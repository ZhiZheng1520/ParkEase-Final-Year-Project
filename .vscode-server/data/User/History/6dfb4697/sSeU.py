from flask import Flask, jsonify
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)

# MySQL connection parameters
db_config = {
    'host': 'tanzhizheng1520.mysql.pythonanywhere-services.com',
    'user': 'tanzhizheng1520',
    'password': 're2Super',
    'database': 'your_database_name'  # Replace with your actual database name
}

@app.route('/')
def home():
    return jsonify(message="Welcome to ParkEase API, JunJun!")

@app.route('/test')
def test():
    return jsonify(message="API is working!")

@app.route('/reservations', methods=['GET'])
def get_reservations():
    try:
        # Establish the connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM reservations;")
            records = cursor.fetchall()

            # Create a list of dictionaries to hold the results
            reservations = []
            for row in records:
                reservations.append({
                    'reservation_id': row[0],
                    'user_id': row[1],
                    'vehicle_id': row[2],
                    'slot_id': row[3],
                    'reservation_start': row[4],
                    'reservation_end': row[5],
                    'status': row[6],
                    'created_at': row[7]
                })

            return jsonify(reservations=reservations)

    except Error as e:
        return jsonify(error=str(e)), 500

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
