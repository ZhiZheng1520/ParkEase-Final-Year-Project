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
# Function to get available slots
def get_available_slots():
    try:
        # Establish the connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Query to get the total number of slots per zone
            cursor.execute("SELECT zone, COUNT(*) AS total_slots FROM parking_slots GROUP BY zone;")
            total_slots_per_zone = cursor.fetchall()

            # Query to get the number of reserved slots per zone
            cursor.execute("""
                SELECT ps.zone, COUNT(r.slot_id) AS reserved_slots
                FROM reservations r
                JOIN parking_slots ps ON r.slot_id = ps.slot_id
                WHERE r.status = 'Reserved'
                GROUP BY ps.zone;
            """)
            reserved_slots_per_zone = cursor.fetchall()

            # Prepare a dictionary to hold the results
            reserved_dict = {row['zone']: row['reserved_slots'] for row in reserved_slots_per_zone}
            available_slots = []

            # Calculate available slots for each zone
            for total in total_slots_per_zone:
                zone = total['zone']
                total_slots = total['total_slots']
                reserved_slots = reserved_dict.get(zone, 0)  # Default to 0 if no reserved slots in this zone
                available_slots.append({
                    'zone': zone,
                    'total_slots': total_slots,
                    'reserved_slots': reserved_slots,
                    'available_slots': total_slots - reserved_slots
                })

            return available_slots

    except Error as e:
        print(f"Error: {e}")
        return None

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()


@app.route('/')
def home():
    logging.debug("Home route accessed")
    return jsonify(message="Welcome to ParkEase API, JunJun!")

@app.route('/available_slots', methods=['GET'])
def available_slots():
    slots = get_available_slots()
    if slots:
        return jsonify(slots)
    else:
        return jsonify({"message": "Error fetching data"}), 500

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
