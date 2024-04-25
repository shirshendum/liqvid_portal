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
    # Assuming 'center_id' is the dropdown column from your_table for dropdown options
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT center_id FROM user_session_tracking")
    dropdown_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template('index.html', dropdown_options=dropdown_options)

@app.route('/update_heatmap', methods=['POST'])
def update_heatmap():
    center_id = request.form['dropdown']
    month = request.form['intParam1']  # Assuming month is entered as intParam1
    year = request.form['intParam2']   # Assuming year is entered as intParam2

    conn = get_db_connection()
    cursor = conn.cursor()
    query = """
        SELECT batch_id, DAY(track_datettime) as day, SUM(actual_seconds)/3600 as hours_spent
        FROM user_session_tracking
        WHERE center_id = %s AND MONTH(track_datettime) = %s AND YEAR(track_datettime) = %s
        GROUP BY DAY(track_datettime), batch_id
    """
    cursor.execute(query, (center_id, month, year))
    data = cursor.fetchall()
    cursor.close()
    conn.close()

    # Creating a DataFrame to properly manage and reshape the data for heatmap generation
    df = pd.DataFrame(data, columns=['batch_id', 'day', 'hours_spent'])
    df['hours_spent'] = df['hours_spent'].astype(float)
    df_pivot = df.pivot("batch_id", "day", "hours_spent")

    # Creating a heatmap using seaborn
    plt.figure(figsize=(10, 8))
    sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
    plt.title("Hours Spent by Batch and Day")
    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    return f'<img src="data:image/png;base64,{plot_url}" />'

if __name__ == '__main__':
    app.run(debug=True)


