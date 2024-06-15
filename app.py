import mysql.connector
import pandas as pd
import os
from flask import Flask, render_template, request, jsonify
import seaborn as sns
import matplotlib.pyplot as plt
import io
import base64
import configparser
from datetime import datetime

app = Flask(__name__)

conf = configparser.ConfigParser()
config_file_path = os.path.join(os.getcwd(), 'configs', 'config_production_db.ini')

#print(config_file_path)
conf.read(config_file_path)

db_host = conf['mysql']['host']
db_user = conf['mysql']['user']
db_pass = conf['mysql']['password']
db_name = conf['mysql']['database']

def get_db_connection():
    return mysql.connector.connect(
        host=db_host,
        user=db_user,
        password= db_pass,
        database=db_name
    )


@app.route('/')
def index():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT DISTINCT region_name FROM rpt_users_test WHERE region_name NOT IN ("Learning Demo", "Globus Digital Language Lab Dummy", "Cambridge Capable Demo", "SchoolNet - Not Used", "Engrezi - Removed") AND region_name IS NOT NULL""")
    region_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    placeholders = ', '.join(['%s']*len(region_options))
    query = """ SELECT region_name, center_name, regd_users, regd_teachers, regd_students, trainer_limit, student_limit, center_created_date, session_start_date, days_remaining, users_added, teachers_added, students_added, hours_spent, hours_teachers, hours_students, num_logins, teacher_logins, student_logins, product, license_key 
    
    FROM
    (SELECT region_id, region_name, center_id, center_name, COUNT(DISTINCT user_id) as regd_users,
    COUNT(DISTINCT CASE WHEN user_role = 'INSTRUCTOR' THEN user_id END) as regd_teachers, trainer_limit,
    COUNT(CASE WHEN user_role = 'LEARNER' THEN 1 END) as regd_students, student_limit, 
    date(center_created_on) as center_created_date, session_start_date, DATEDIFF(session_end_date, CURDATE()) AS days_remaining, product, license_key
    
    FROM rpt_users_test WHERE region_name IN (%s) AND status = 1 group by region_id, center_id) rut
    
    LEFT JOIN (SELECT center_id, day, month, year, ROUND((SUM(actual_seconds)/3600), 1) AS hours_spent, 
    ROUND((SUM(CASE WHEN user_role = 'INSTRUCTOR' THEN actual_seconds ELSE 0 END)/3600), 1) AS hours_teachers, 
    ROUND((SUM(CASE WHEN user_role = 'LEARNER' THEN actual_seconds ELSE 0 END)/3600), 1) AS hours_students FROM rpt_hierarchical_usage GROUP BY center_id) rhu on rhu.center_id = rut.center_id
    
    LEFT JOIN (SELECT center_id, day, month, year, 
    COUNT(*) AS num_logins, COUNT(CASE WHEN user_role = 'INSTRUCTOR' THEN 1 ELSE NULL END) AS teacher_logins, 
    COUNT(CASE WHEN user_role = 'LEARNER' THEN 1 ELSE NULL END) AS student_logins FROM rpt_hierarchical_logins GROUP BY center_id) rhl on rhl.center_id = rut.center_id
    
    LEFT JOIN (SELECT center_id, COUNT(DISTINCT user_id) AS users_added, 
    COUNT(DISTINCT CASE WHEN user_role = 'INSTRUCTOR' THEN user_id ELSE NULL END) AS teachers_added, COUNT(DISTINCT CASE WHEN user_role = 'LEARNER' THEN user_id ELSE NULL END) AS students_added FROM `rpt_users_test`
    GROUP BY center_id) rut2 ON rut2.center_id = rut.center_id
    """ % placeholders
    cursor.execute(query, region_options)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('index.html', region_options = region_options, data = rows)
 
@app.route('/get_batches', methods=['POST'])
def get_batches():
    region_name = request.form['region']
    center_name = request.form['center']
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT DISTINCT batch_name FROM rpt_flat_usage WHERE region_name = %s AND center_name = %s"
    cursor.execute(query, (region_name, center_name, ))
    batch_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    return jsonify(batch_options)
    
def fetch_centers(region_name):
    """Utility function to fetch center names based on the region."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT DISTINCT center_name FROM rpt_flat_usage WHERE region_name = %s"
    cursor.execute(query, (region_name,))
    center_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    return center_options

@app.route('/get_centers', methods=['POST'])
def get_centers():
    region_name = request.form['region']
    center_options = fetch_centers(region_name)
    return jsonify(center_options)

def fetch_batches(center_name):
    """Utility function to fetch batch names based on the center."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT DISTINCT batch_name FROM rpt_flat_usage WHERE center_name = %s"
    cursor.execute(query, (center_name,))
    batch_options = [item[0] for item in cursor.fetchall()]
    cursor.close()
    conn.close()
    return batch_options

@app.route('/update_heatmap', methods=['POST'])
def update_heatmap():
    region = request.form['regionDropdown'] if 'regionDropdown' in request.form and request.form['regionDropdown'] else None
    center = request.form['centerDropdown'] if 'centerDropdown' in request.form and request.form['centerDropdown'] else None
    month = request.form['month']
    year = request.form['year']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    if region:

        if center:
            query = """
            SELECT batch_name, day, usage_hours as hours_spent
            FROM rpt_flat_usage
            WHERE region_name = %s AND center_name = %s AND month = %s AND year = %s
            """
            # GROUP BY day, batch_name
        
            query2 = """
            SELECT batch_name, day, login_count as num_logins
            FROM rpt_flat_logins
            WHERE region_name = %s AND center_name = %s AND month = %s AND year = %s
            """
            # GROUP BY day, batch_name
            cursor.execute(query, (region, center, month, year))
            data = cursor.fetchall()
            df = pd.DataFrame(data, columns=['batch_name', 'day', 'hours_spent'])
        
            cursor.execute(query2, (region, center, month, year))
            data2 = cursor.fetchall()
            df2 = pd.DataFrame(data, columns=['batch_name', 'day', 'num_logins'])
            #all_categories = pd.DataFrame({'batch_name': fetch_batches(center)})
        else:
            query = """
            SELECT center_name, day, SUM(usage_hours) as hours_spent
            FROM rpt_flat_usage
            WHERE region_name = %s AND month = %s AND year = %s
            GROUP BY day, center_name
            """
            query2 = """
            SELECT center_name, day, SUM(login_count) as num_logins
            FROM rpt_flat_logins
            WHERE region_name = %s AND month = %s AND year = %s
            GROUP BY day, center_name
            """
            cursor.execute(query, (region, month, year))
            data = cursor.fetchall()
            df = pd.DataFrame(data, columns=['center_name', 'day', 'hours_spent'])

            cursor.execute(query2, (region, month, year))
            data2 = cursor.fetchall()
            df2 = pd.DataFrame(data, columns=['center_name', 'day', 'num_logins'])
            #all_categories = pd.DataFrame({'center_name': fetch_centers(region)})
            
    else:
        query = """
            SELECT region_name, day, SUM(usage_hours) as hours_spent
            FROM rpt_flat_usage
            WHERE month = %s AND year = %s
            GROUP BY day, region_name """
        cursor.execute(query, (month, year))
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['reseller_name', 'day', 'hours_spent'])
        
    cursor.close()
    conn.close()

    df['hours_spent'] = df['hours_spent'].astype(float)

        # Ensure all days of the month are included
        #all_days = pd.DataFrame({'day': range(1, 32)})
        #all_categories = pd.DataFrame({'category': df['category'].unique()})
        #all_combinations = pd.merge(all_categories.assign(key=1), all_days.assign(key=1), on='key').drop('key', 1)
        #full_df = pd.merge(all_combinations, df, how='left', on=['category', 'day']).fillna(0)

    if region:
    
        if center:
            #full_df = pd.merge(all_combinations, df, how='left', on=['batch_name', 'day']).fillna(0)
            df_pivot = df.pivot("batch_name", "day", "hours_spent")
            plt.figure(figsize=(24, 10))
            sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
            plt.title("Hours Spent by Batch")
        else:
            #full_df = pd.merge(all_combinations, df, how='left', on=['center_name', 'day']).fillna(0)
            df_pivot = df.pivot("center_name", "day", "hours_spent")
            plt.figure(figsize=(24, 10))
            sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
            plt.title("Hours Spent by Center")
    else:
        df_pivot = df.pivot("reseller_name", "day", "hours_spent")
        plt.figure(figsize=(24, 10))
        sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
        plt.title("Hours Spent by Reseller")

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    return f'<img src="data:image/png;base64,{plot_url}" />'
   

@app.route('/update_heatmap2', methods=['POST'])
def update_heatmap2():
    region = request.form['regionDropdown'] if 'regionDropdown' in request.form and request.form['regionDropdown'] else None
    #center = request.form['centerDropdown'] if 'centerDropdown' in request.form and request.form['centerDropdown'] else None
    month = request.form['month']
    year = request.form['year']

    conn = get_db_connection()
    cursor = conn.cursor()
    
    if region:
        query = """
            SELECT center_name, day, SUM(login_count) as num_logins
            FROM rpt_flat_logins
            WHERE region_name = %s AND month = %s AND year = %s
            GROUP BY day, center_name
        """
        cursor.execute(query, (region, month, year))
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['center_name', 'day', 'num_logins'])
            
    else:
        query = """
            SELECT region_name, day, SUM(login_count) as num_logins
            FROM rpt_flat_logins
            WHERE month = %s AND year = %s
            GROUP BY day, region_name """
        cursor.execute(query, (month, year))
        data = cursor.fetchall()
        df = pd.DataFrame(data, columns=['reseller_name', 'day', 'num_logins'])
        
    cursor.close()
    conn.close()
    df['num_logins'] = df['num_logins'].astype(int)
    
    if region:
        df_pivot = df.pivot("center_name", "day", "num_logins")
        plt.figure(figsize=(24, 10))
        sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
        plt.title("Logins by Center")

    else:
        df_pivot = df.pivot("reseller_name", "day", "num_logins")
        plt.figure(figsize=(24, 10))
        sns.heatmap(df_pivot, annot=True, fmt=".1f", cmap="YlGnBu", linewidths=.5)
        plt.title("Logins by Reseller")

    img = io.BytesIO()
    plt.savefig(img, format='png', bbox_inches='tight')
    img.seek(0)
    plot_url = base64.b64encode(img.getvalue()).decode('utf8')
    return f'<img src="data:image/png;base64,{plot_url}" />'


@app.route('/filter_data_table', methods=['POST'])
def filter_data_table():
    region = request.form['tableRegionDropdown'] if 'tableRegionDropdown' in request.form and request.form['tableRegionDropdown'] else None
    start_date = request.form.get('startDate')
    end_date = request.form.get('endDate')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""SELECT DISTINCT region_name FROM rpt_users_test WHERE region_name NOT IN ("Learning Demo", "Globus Digital Language Lab Dummy", "Cambridge Capable Demo", "SchoolNet - Not Used", "Engrezi - Removed") AND region_name IS NOT NULL""")
    region_options = [item[0] for item in cursor.fetchall()]
    placeholders = ', '.join(['%s']*len(region_options))
    cursor.close()
    conn.close()

# Parse the start and end dates into components
    start_year, start_month, start_day = map(int, start_date.split('-'))
    end_year, end_month, end_day = map(int, end_date.split('-'))

    
    if region is None:
        print(region)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary = True)
        query = """SELECT region_name, center_name, regd_users, regd_teachers, regd_students, trainer_limit, student_limit, center_created_date, session_start_date, days_remaining, users_added, teachers_added, students_added, hours_spent, hours_teachers, hours_students, num_logins, teacher_logins, student_logins, product, license_key FROM
    (SELECT region_id, region_name, center_id, center_name, trainer_limit, student_limit, date(center_created_on) as center_created_date, session_start_date,
    DATEDIFF(session_end_date, CURDATE()) AS days_remaining, COUNT(DISTINCT user_id) as regd_users,
    COUNT(DISTINCT CASE WHEN user_role = 'INSTRUCTOR' THEN user_id END) as regd_teachers,
    COUNT(CASE WHEN user_role = 'LEARNER' THEN 1 END) as regd_students, product, license_key
    FROM rpt_users_test WHERE region_name IN ({}) AND status = 1 GROUP BY region_id, center_id) rut
    
    LEFT JOIN (SELECT center_id, day, month, year, ROUND((SUM(actual_seconds)/3600), 1) AS hours_spent, ROUND((SUM(CASE WHEN user_role = 'INSTRUCTOR' THEN actual_seconds ELSE 0 END)/3600), 1) AS hours_teachers, ROUND((SUM(CASE WHEN user_role = 'LEARNER' THEN actual_seconds ELSE 0 END)/3600), 1) AS hours_students FROM rpt_hierarchical_usage 
    WHERE (year > %s OR (year = %s AND month > %s) OR (year = %s AND month = %s AND day >= %s))
    AND (year < %s OR (year = %s AND month < %s) OR (year = %s AND month = %s AND day <= %s))
    GROUP BY center_id) rhu on rhu.center_id = rut.center_id
    
    LEFT JOIN (SELECT center_id, day, month, year, COUNT(*) AS num_logins, COUNT(CASE WHEN user_role = 'INSTRUCTOR' THEN 1 ELSE NULL END) AS teacher_logins, COUNT(CASE WHEN user_role = 'LEARNER' THEN 1 ELSE NULL END) AS student_logins FROM rpt_hierarchical_logins 
    WHERE (year > %s OR (year = %s AND month > %s) OR (year = %s AND month = %s AND day >= %s))
    AND (year < %s OR (year = %s AND month < %s) OR (year = %s AND month = %s AND day <= %s))
    GROUP BY center_id) rhl on rhl.center_id = rut.center_id
    
    LEFT JOIN (SELECT center_id, COUNT(DISTINCT user_id) AS users_added, 
    COUNT(DISTINCT CASE WHEN user_role = 'INSTRUCTOR' THEN user_id ELSE NULL END) AS teachers_added, COUNT(DISTINCT CASE WHEN user_role = 'LEARNER' THEN user_id ELSE NULL END) AS students_added FROM `rpt_users_test`
    WHERE (year(user_created_on) > %s OR (year(user_created_on) = %s AND month(user_created_on) > %s) OR (year(user_created_on) = %s AND month(user_created_on) = %s AND day(user_created_on) >= %s))
    AND (year(user_created_on) < %s OR (year(user_created_on) = %s AND month(user_created_on) < %s) OR (year(user_created_on) = %s AND month(user_created_on) = %s AND day(user_created_on) <= %s))
    GROUP BY center_id) rut2 ON rut2.center_id = rut.center_id
        """.format(placeholders)

        params = region_options + [start_year, start_year, start_month, start_year, start_month, start_day, end_year, end_year, end_month, end_year, end_month, end_day, start_year, start_year, start_month, start_year, start_month, start_day, end_year, end_year, end_month, end_year, end_month, end_day, start_year, start_year, start_month, start_year, start_month, start_day, end_year, end_year, end_month, end_year, end_month, end_day]
        #print(region_options)
        cursor.execute(query, params)
        rows = cursor.fetchall()
        #print(len(rows))
        print(len(region_options))
        cursor.close()
        conn.close()
        
    if region:
        # Extend the query to include a filter by the selected reseller
        print(region)
        conn = get_db_connection()
        cursor = conn.cursor(dictionary = True)
        query = """SELECT region_name, center_name, regd_users, regd_teachers, regd_students, trainer_limit, student_limit, center_created_date, session_start_date, days_remaining, users_added, teachers_added, students_added, hours_spent, hours_teachers, hours_students, num_logins, teacher_logins, student_logins, product, license_key 
        
    FROM (SELECT region_id, region_name, center_id, center_name, COUNT(DISTINCT user_id) as regd_users,
    COUNT(DISTINCT CASE WHEN user_role = 'INSTRUCTOR' THEN user_id END) as regd_teachers, trainer_limit,
    COUNT(CASE WHEN user_role = 'LEARNER' THEN 1 END) as regd_students, student_limit, 
    date(center_created_on) as center_created_date, session_start_date, DATEDIFF(session_end_date, CURDATE()) AS days_remaining, product, license_key
    FROM rpt_users_test 
    WHERE region_name = %s AND status = 1 GROUP BY region_id, center_id) rut
    
    LEFT JOIN (SELECT center_id, day, month, year, ROUND((SUM(actual_seconds)/3600), 1) AS hours_spent, 
    ROUND((SUM(CASE WHEN user_role = 'INSTRUCTOR' THEN actual_seconds ELSE 0 END)/3600), 1) AS hours_teachers, 
    ROUND((SUM(CASE WHEN user_role = 'LEARNER' THEN actual_seconds ELSE 0 END)/3600), 1) AS hours_students FROM rpt_hierarchical_usage 
    WHERE (year > %s OR (year = %s AND month > %s) OR (year = %s AND month = %s AND day >= %s))
    AND (year < %s OR (year = %s AND month < %s) OR (year = %s AND month = %s AND day <= %s))
    GROUP BY center_id) rhu on rhu.center_id = rut.center_id
    
    LEFT JOIN (SELECT center_id, day, month, year, COUNT(*) AS num_logins, 
    COUNT(CASE WHEN user_role = 'INSTRUCTOR' THEN 1 ELSE NULL END) AS teacher_logins, COUNT(CASE WHEN user_role = 'LEARNER' THEN 1 ELSE NULL END) AS student_logins FROM rpt_hierarchical_logins 
    WHERE (year > %s OR (year = %s AND month > %s) OR (year = %s AND month = %s AND day >= %s))
    AND (year < %s OR (year = %s AND month < %s) OR (year = %s AND month = %s AND day <= %s))
    GROUP BY center_id) rhl on rhl.center_id = rut.center_id
    
    LEFT JOIN (SELECT center_id, COUNT(DISTINCT user_id) AS users_added, 
    COUNT(DISTINCT CASE WHEN user_role = 'INSTRUCTOR' THEN user_id ELSE NULL END) AS teachers_added, COUNT(DISTINCT CASE WHEN user_role = 'LEARNER' THEN user_id ELSE NULL END) AS students_added FROM `rpt_users_test`
    WHERE (year(user_created_on) > %s OR (year(user_created_on) = %s AND month(user_created_on) > %s) OR (year(user_created_on) = %s AND month(user_created_on) = %s AND day(user_created_on) >= %s))
    AND (year(user_created_on) < %s OR (year(user_created_on) = %s AND month(user_created_on) < %s) OR (year(user_created_on) = %s AND month(user_created_on) = %s AND day(user_created_on) <= %s))
    GROUP BY center_id) rut2 ON rut2.center_id = rut.center_id
    """
        params = [region, start_year, start_year, start_month, start_year, start_month, start_day, end_year, end_year, end_month, end_year, end_month, end_day, start_year, start_year, start_month, start_year, start_month, start_day, end_year, end_year, end_month, end_year, end_month, end_day, start_year, start_year, start_month, start_year, start_month, start_day, end_year, end_year, end_month, end_year, end_month, end_day]

        cursor.execute(query, params)
        rows = cursor.fetchall()
        cursor.close()
        conn.close()
        print(len(rows))
    #return render_template('index.html', region_options = region_options, data = rows)
    return jsonify([dict(row) for row in rows])
        
        
@app.route('/last_updated_date', methods=['GET'])
def last_updated_date():
    conn = get_db_connection()
    cursor = conn.cursor()
    # Query to fetch the last updated date; adjust table and column names as necessary
    cursor.execute("SELECT MIN(timestamp) FROM rpt_users_test")
    last_updated = cursor.fetchone()[0]
    cursor.close()
    conn.close()

    if last_updated:
        # Formatting the date if it exists
        return jsonify({'lastUpdated': last_updated.strftime('%Y-%m-%d')})
    else:
        return jsonify({'lastUpdated': 'No data available'})

        
if __name__ == '__main__':
    env = os.getenv('FLASK_ENV', 'development')
    debug_mode = (env == 'development')
    app.run(host = '0.0.0.0', port = 5000, debug=debug_mode)


