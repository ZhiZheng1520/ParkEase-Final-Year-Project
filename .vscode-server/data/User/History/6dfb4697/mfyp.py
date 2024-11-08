from flask import Flask, jsonify
import mysql.connector
from mysql.connector import Error
import logging

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# MySQL connection parameters
db_config = {
    'host': 'tanzhizheng1520.mysql.pythonanywhere-services.com',
    'user': 'tanzhizheng1520',
    'password': 're2Super',
    'database': 'tanzhizheng1520$ParkEase'  # Replace with your actual database name
}

@app.route('/')
def home():
    logging.debug("Home route accessed")
    return jsonify(message="Welcome to ParkEase API, JunJun!")

@app.route('/test')
def test():
    logging.debug("Test route accessed")
    return jsonify(message="API is working!")

@app.route('/sqltest', methods=['GET'])
def get_reservations():
    try:
        # Establish the connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            logging.debug("Successfully connected to the MySQL database.")

            # Create a cursor object
            cursor = connection.cursor()

            # Execute the SELECT query
            cursor.execute("SELECT * FROM reservations;")

            # Fetch all the records
            records = cursor.fetchall()

            # Prepare the result in JSON format
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

            # Close the cursor
            cursor.close()

            # Return the reservations as JSON
            return jsonify(reservations=reservations)

        else:
            logging.error("Failed to connect to the MySQL database.")
            return jsonify(error="Failed to connect to the database."), 500

    except Error as e:
        logging.error(f"Database error occurred: {e}")
        return jsonify(error=str(e)), 500

    finally:
        # Close the connection if it was established
        if 'connection' in locals() and connection.is_connected():
            connection.close()
            logging.debug("MySQL connection is closed.")

if __name__ == '__main__':
    logging.debug("Starting the Flask application")
    app.run(host='0.0.0.0', port=5000)
