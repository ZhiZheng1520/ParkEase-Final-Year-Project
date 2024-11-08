from flask import Flask, jsonify, request
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
    return jsonify(message="Welcome to ParkEase API!")

@app.route('/slotleft', methods=['GET'])
def available_slots():
    slots = get_available_slots()
    if slots:
        return jsonify(slots)
    else:
        return jsonify({"message": "Error fetching data"}), 500

@app.route('/reservations', methods=['GET'])
def get_reservations_by_filter():
    """
    API to get reservation details filtered by location, reservation start, and end date.
    URL parameters:
      - location: string (e.g., "APU Carpark B")
      - reservation_start: date (e.g., "2024-01-01")
      - reservation_end: date (e.g., "2024-12-31")
    """
    try:
        # Establish the connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            logging.debug("Successfully connected to the MySQL database.")

            # Get query parameters
            location = request.args.get('location')
            reservation_start = request.args.get('reservation_start')
            reservation_end = request.args.get('reservation_end')

            # Create a cursor object
            cursor = connection.cursor(dictionary=True)

            # Base SQL query
            query = """
                SELECT r.*, ps.zone, ps.location
                FROM reservations r
                JOIN parking_slots ps ON r.slot_id = ps.slot_id
                WHERE 1=1
            """

            # Add filters if provided
            params = []
            if location:
                query += " AND ps.location = %s"
                params.append(location)
            if reservation_start:
                query += " AND r.reservation_start >= %s"
                params.append(reservation_start)
            if reservation_end:
                query += " AND r.reservation_end <= %s"
                params.append(reservation_end)

            # Execute the query with parameters
            cursor.execute(query, params)

            # Fetch all the records
            records = cursor.fetchall()

            # Prepare the result in JSON format
            reservations = []
            for row in records:
                reservations.append({
                    'reservation_id': row['reservation_id'],
                    'user_id': row['user_id'],
                    'vehicle_id': row['vehicle_id'],
                    'slot_id': row['slot_id'],
                    'reservation_start': row['reservation_start'],
                    'reservation_end': row['reservation_end'],
                    'status': row['status'],
                    'created_at': row['created_at'],
                    'zone': row['zone'],
                    'location': row['location']
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
