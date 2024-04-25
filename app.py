from flask import Flask, render_template, request, jsonify
import mysql.connector
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)

def get_db_connection():
    return mysql.connector.connect(
        host='4.224.251.12',
        user='root',
        password= 'QR5L1Ri2DXxp',
        database='production_db'
    )

@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT region_name FROM rpt_hierarchical_usage")
    region_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template('index.html', region_options=region_options)

@app.route('/get_centers', methods=['POST'])
def get_centers():
    region_name = request.form['region']
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT DISTINCT center_name FROM rpt_hierarchical_usage WHERE region_name = %s"
    cursor.execute(query, (region_name,))
    center_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(center_options)

@app.route('/update_heatmap', methods=['POST'])
def update_heatmap():
    region = request.form['regionDropdown']
    center = request.form['centerDropdown'] if 'centerDropdown' in request.form and request.form['centerDropdown'] else None
    month = request.form['month']
    year = request.form['year']

    conn = get_db_connection()
    cursor = conn.cursor()

    if center:
        query = """
            SELECT batch_name, day, SUM(actual_seconds)/3600 as hours_spent
            FROM rpt_hierarchical_usage
            WHERE region_name = %s AND center_name = %s AND month = %s AND year = %s
            GROUP BY day, batch_name
        """
        cursor.execute(query, (region, center, month, year))
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['batch_name', 'day', 'hours_spent'])
    else:
        query = """
            SELECT center_name, day, SUM(actual_seconds)/3600 as hours_spent
            FROM rpt_hierarchical_usage
            WHERE region_name = %s AND month = %s AND year = %s
            GROUP BY day, center_name
        """
        cursor.execute(query, (region, month, year))
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['center_name', 'day', 'hours_spent'])
    cursor.close()
    conn.close()

    df['hours_spent'] = df['hours_spent'].astype(float)  # Convert Decimal to float

    if center:
        df_pivot = df.pivot("batch_name", "day", "hours_spent")
        plt.figure(figsize=(10, 8))
        sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
        plt.title("Hours Spent by batch_name and Day")
    else:
        df_pivot = df.pivot("center_name", "day", "hours_spent")
        plt.figure(figsize=(10, 8))
        sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
        plt.title("Hours Spent by center_name and Day")

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    return f'<img src="data:image/png;base64,{plot_url}" />'
    
if __name__ == '__main__':
    app.run(debug=True)


