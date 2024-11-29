from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime, timedelta  # Ensure this import exists
import time
import networkx as nx
import heapq
import pytz

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# MySQL connection parameters
db_config = {
    'host': 'tanzhizheng1520.mysql.pythonanywhere-services.com',
    'user': 'tanzhizheng1520',
    'password': 're2Super',
    'database': 'tanzhizheng1520$ParkEase'
}

def create_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            logging.debug("Connected to MySQL database")
            return connection
    except Error as e:
        logging.error(f"Error connecting to MySQL: {e}")
        return None
@app.route('/addcarplate', methods=['POST'])
def add_carplate():
    """API endpoint to add a new carplate for a user"""
    try:
        # Parse input data (JSON body)
        data = request.get_json()

        # Extract carplate and user_id from the request body
        carplate = data.get('carplate')
        user_id = data.get('user_id')

        # Check if carplate and user_id are provided
        if not carplate or not user_id:
            return jsonify({"message": "Please provide both carplate and user_id"}), 400

        # Establish the database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor()

            # Insert the carplate and user_id into the vehicles table
            insert_query = """
                INSERT INTO vehicles (carplate, user_id, created_at)
                VALUES (%s, %s, %s)
            """
            created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')  # Get the current UTC time
            cursor.execute(insert_query, (carplate, user_id, created_at))
            connection.commit()

            # Success response
            return jsonify({"message": "Carplate added successfully"}), 201

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error adding carplate", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

# Simplified function to calculate price and duration (no strptime needed)
# Simplified function to calculate price and duration with 2 decimal points as floats
def calculate_price_and_duration(start_time, end_time):
    # Since start_time and end_time are already datetime objects, calculate directly
    duration_hours = round((end_time - start_time).total_seconds() / 3600, 2)  # Round to 2 decimal points
    price = round(duration_hours * 2, 2)  # RM2 per hour, round to 2 decimals
    return duration_hours, price



def get_available_slots(location, start_time, end_time):
    try:
        # Establish the connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Query to get all slots by zone for the specified location
            cursor.execute("""
                SELECT slot_id, zone
                FROM parking_slots
                WHERE location = %s AND allow_reservation = "true";
            """, (location,))
            all_slots = cursor.fetchall()

            # Query to get reserved slots within the specified time range
            cursor.execute("""
                SELECT r.slot_id, ps.zone, r.reservation_start, r.reservation_end
                FROM reservations r
                JOIN parking_slots ps ON r.slot_id = ps.slot_id
                WHERE ps.location = %s
                AND r.status = 'Reserved'
                AND (
                    (%s BETWEEN r.reservation_start AND r.reservation_end) OR
                    (%s BETWEEN r.reservation_start AND r.reservation_end) OR
                    (r.reservation_start BETWEEN %s AND %s) OR
                    (r.reservation_end BETWEEN %s AND %s)
                );
            """, (location, start_time, end_time, start_time, end_time, start_time, end_time))
            reserved_slots = cursor.fetchall()

            # Prepare dictionaries to count reserved slots and available slots by zone
            reserved_slots_by_zone = {}
            all_slots_by_zone = {}

            for slot in all_slots:
                zone = slot['zone']
                slot_id = slot['slot_id']
                if zone not in all_slots_by_zone:
                    all_slots_by_zone[zone] = []
                all_slots_by_zone[zone].append(slot_id)

            for row in reserved_slots:
                zone = row['zone']
                slot_id = row['slot_id']
                if zone not in reserved_slots_by_zone:
                    reserved_slots_by_zone[zone] = []
                reserved_slots_by_zone[zone].append(slot_id)

            # Include all zones, even those without any slots (e.g., available_slots = 0)
            available_slots = []
            for zone, slots in all_slots_by_zone.items():
                reserved_in_zone = set(reserved_slots_by_zone.get(zone, []))  # Get reserved slots for the zone
                available_in_zone = [slot for slot in slots if slot not in reserved_in_zone]  # Filter out reserved slots
                available_slots.append({
                    'zone': zone,
                    'total_slots': len(slots),
                    'reserved_slots': len(reserved_in_zone),
                    'available_slots': len(available_in_zone),
                    'reserved_slot_ids': list(reserved_in_zone),
                    'available_slot_ids': available_in_zone
                })

            # Ensure all zones are shown, even if no slots exist for them
            all_zones = set(all_slots_by_zone.keys())
            included_zones = set([slot['zone'] for slot in available_slots])
            missing_zones = all_zones - included_zones

            for zone in missing_zones:
                available_slots.append({
                    'zone': zone,
                    'total_slots': 0,
                    'reserved_slots': 0,
                    'available_slots': 0,
                    'reserved_slot_ids': [],
                    'available_slot_ids': []
                })

            # Sort by zone to ensure consistent output order
            available_slots = sorted(available_slots, key=lambda x: x['zone'])

            return available_slots

    except Error as e:
        logging.error(f"Error: {e}")
        return None

    finally:
        if 'connection' in locals() and connection.is_connected():
            connection.close()

@app.route('/')
def home():
    logging.debug("Home route accessed")
    return jsonify(message="Welcome to ParkEase API!")

# Slot left endpoint for available slots
@app.route('/slotleft/<string:location>', methods=['GET'])
def available_slots(location):
    # Extract the start_time and end_time from the query parameters
    start_time = request.args.get('start_time')
    end_time = request.args.get('end_time')

    # Check if start_time and end_time were provided
    if not start_time or not end_time:
        return jsonify({"message": "Please provide both start_time and end_time in the query parameters"}), 400

    # Fetch available slots for the given location and time range
    slots = get_available_slots(location, start_time, end_time)
    if slots:
        return jsonify(slots)
    else:
        return jsonify({"message": "Error fetching data"}), 500

@app.route('/selectedslot/<string:location>', methods=['GET'])
def selected_slot(location):
    # Extract the start_time, end_time, and zone from the query parameters
    start_time_str = request.args.get('start_time')
    end_time_str = request.args.get('end_time')
    zone = request.args.get('zone')

    # Log the parameters to check if they are received correctly
    logging.debug(f"Location: {location}, Start Time: {start_time_str}, End Time: {end_time_str}, Zone: {zone}")

    # Check if all parameters are provided
    if not all([start_time_str, end_time_str, zone]):
        return jsonify({"message": "Please provide start_time, end_time, and zone"}), 400

    try:
        # Parse the start and end times from the request (strings to datetime)
        start_time = datetime.strptime(start_time_str, "%Y-%m-%d %H:%M:%S")
        end_time = datetime.strptime(end_time_str, "%Y-%m-%d %H:%M:%S")

        # Establish the MySQL connection
        connection = mysql.connector.connect(**db_config)

        if connection.is_connected():
            cursor = connection.cursor(dictionary=True)

            # Log before running the SQL query
            logging.debug("Executing SQL query to fetch reservations and slots...")

            # Query to get all slots in the specified location and zone
            cursor.execute("""
                SELECT slot_id
                FROM parking_slots
                WHERE location = %s AND zone = %s AND allow_reservation = "true";
            """, (location, zone))
            all_slots = [row['slot_id'] for row in cursor.fetchall()]  # All slot IDs in the zone

            # Query to get reserved slots within the specified time range
            cursor.execute("""
                SELECT r.slot_id
                FROM reservations r
                JOIN parking_slots ps ON r.slot_id = ps.slot_id
                WHERE ps.location = %s AND ps.zone = %s
                AND r.status = 'Reserved'
                AND (
                    (%s BETWEEN r.reservation_start AND r.reservation_end) OR
                    (%s BETWEEN r.reservation_start AND r.reservation_end) OR
                    (r.reservation_start BETWEEN %s AND %s) OR
                    (r.reservation_end BETWEEN %s AND %s)
                );
            """, (location, zone, start_time, end_time, start_time, end_time, start_time, end_time))
            reserved_slots = [row['slot_id'] for row in cursor.fetchall()]  # Reserved slot IDs

            # Get available slots by excluding reserved slots from all slots
            available_slots = [slot for slot in all_slots if slot not in reserved_slots]

            # Log the available slot IDs
            logging.debug(f"Available slots in zone {zone}: {available_slots}")

            if available_slots:
                # Find the smallest available slot ID
                smallest_slot_id = min(available_slots)

                # Calculate the duration and price for the given time range
                duration_hours, price = calculate_price_and_duration(start_time, end_time)

                # Return the reservation details for the smallest available slot
                result = {
                    'slot_id': smallest_slot_id,
                    'zone': zone,
                    'reservation_start': start_time_str,  # Use the provided start_time
                    'reservation_end': end_time_str,  # Use the provided end_time
                    'duration_hours': duration_hours,
                    'price_rm': price
                }

                return jsonify(result)

            else:
                return jsonify({"message": "No available slots found"}), 404

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching data", "error": str(e)}), 500


    finally:
        # Close the MySQL connection
        if 'connection' in locals() and connection.is_connected():
            connection.close()
@app.route('/getvehicle', methods=['GET'])
def get_vehicle():
    """API endpoint to fetch vehicle information by user_id only"""
    try:
        # Establish the database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)

            # Get the user_id from query parameters
            user_id = request.args.get('user_id')
            show_addcarplate = request.args.get('show_addcarplate')  # Fetch the parameter show_addcarplate

            # If user_id is not provided, return an error
            if not user_id:
                return jsonify({"message": "Please provide a user_id in the query parameters"}), 400

            # Fetch vehicles based on the provided user_id
            cursor.execute("SELECT * FROM vehicles WHERE user_id = %s", (user_id,))
            vehicles = cursor.fetchall()

            # If no vehicle found, return an empty list
            if not vehicles:
                vehicles = []

            # Conditionally append the "Add Carplate" entry based on show_addcarplate
            if show_addcarplate == '1':
                vehicles.append({
                    "carplate": "Add Carplate",
                    "created_at": "",
                    "user_id": user_id
                })

            # Return the updated vehicles list
            return jsonify(vehicles), 200

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching vehicle data", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

# Route to post userid and email
@app.route('/post_userid', methods=['POST'])
def post_userid():
    data = request.json  # Get JSON data from the request body
    if not data:
        return jsonify({"message": "Invalid input. JSON body is required"}), 400

    userid = data.get('userid')
    email = data.get('email')

    # Validate input
    if not userid or not email:
        return jsonify({"message": "Missing userid or email"}), 400

    # Establish database connection
    connection = create_connection()
    if connection:
        try:
            cursor = connection.cursor()

            # Ensure 'users' table exists, or adapt based on your database structure
            insert_query = """
            INSERT INTO users (user_id, email, created_at)
            VALUES (%s, %s, NOW())
            """
            cursor.execute(insert_query, (userid, email))
            connection.commit()  # Commit the transaction to persist the data

            return jsonify({"message": "User added successfully"}), 201
        except Error as e:
            logging.error(f"Error inserting data: {e}")
            return jsonify({"message": "Error adding user to the database", "error": str(e)}), 500
        finally:
            cursor.close()  # Ensure cursor is closed
            connection.close()  # Close the connection
    else:
        return jsonify({"message": "Database connection failed"}), 500

@app.route('/getwalletamount', methods=['GET'])
def get_wallet_amount():
    """API endpoint to get the wallet amount for a user"""
    try:
        # Establish the database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)

            # Get the user_id from query parameters
            user_id = request.args.get('user_id')

            # If user_id is not provided, return an error
            if not user_id:
                return jsonify({"message": "Please provide a user_id in the query parameters"}), 400

            # Fetch the wallet amount based on the provided user_id
            cursor.execute("SELECT wallet_amount FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()

            # If no record is found, return an error
            if result:
                # Format wallet amount to 2 decimal places
                wallet_amount = "{:.2f}".format(result['wallet_amount'])
                return jsonify({"user_id": user_id, "wallet_amount": wallet_amount}), 200
            else:
                return jsonify({"message": f"No wallet information found for user_id {user_id}"}), 404

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching wallet amount", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
@app.route('/updatewalletamount', methods=['POST'])
def update_wallet_amount():
    """API endpoint to add or deduct an amount from the wallet for a user"""
    try:
        # Parse input data (JSON body)
        data = request.get_json()

        # Extract user_id, amount, type, description, and datetime from the request body
        user_id = data.get('user_id')
        amount_str = data.get('amount')  # This is now expected to be a string
        transaction_type = data.get('type')  # "add" or "deduct"
        description = data.get('description')  # New description field
        transaction_datetime = data.get('datetime', datetime.now())  # Optional datetime field

        # Check if user_id, amount, type, and description are provided
        if not user_id or not amount_str or transaction_type not in ["add", "deduct"]:
            return jsonify({"message": "Please provide user_id, amount, type (add or deduct), and description"}), 400

        # Convert amount from string to a positive float and round to 2 decimal places
        try:
            amount = round(abs(float(amount_str)), 2)
        except ValueError:
            return jsonify({"message": "Amount must be a valid number"}), 400

        # If the transaction is a Booking Refund, calculate 40% of the amount
        if transaction_type == "add" and description == "Booking Refund":
            amount = round(amount * 0.4, 2)

        # Set amount negative if the transaction type is "deduct"
        if transaction_type == "deduct":
            amount = -amount

        # Establish the database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)

            # Fetch the current wallet amount for the user
            cursor.execute("SELECT wallet_amount FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()

            if result:
                # Calculate the new wallet amount
                new_wallet_amount = round(result['wallet_amount'] + amount, 2)
                if new_wallet_amount < 0:
                    return jsonify({"message": "Insufficient funds"}), 400

                # Update the wallet amount in users table
                update_query = "UPDATE users SET wallet_amount = %s WHERE user_id = %s"
                cursor.execute(update_query, (new_wallet_amount, user_id))

                # Insert the transaction into the transaction table with description and datetime
                insert_transaction_query = """
                    INSERT INTO transaction (txid, uid, amount, description, datetime)
                    VALUES (UUID(), %s, %s, %s, %s)
                """
                cursor.execute(insert_transaction_query, (user_id, amount, description, transaction_datetime))
                connection.commit()

                return jsonify({"message": "Wallet updated successfully", "new_wallet_amount": new_wallet_amount}), 200
            else:
                return jsonify({"message": f"No user found for user_id {user_id}"}), 404

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error updating wallet amount", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()



@app.route('/removecarplate', methods=['DELETE'])
def remove_carplate():
    """API endpoint to remove a carplate based on query parameters for carplate and user_id"""
    try:
        # Get carplate and user_id from query parameters
        carplate = request.args.get('carplate')
        user_id = request.args.get('user_id')

        # Log the received values
        logging.debug(f"carplate: {carplate}, user_id: {user_id}")

        # Check if both carplate and user_id are provided
        if not carplate or not user_id:
            return jsonify({"message": "Please provide both carplate and user_id"}), 400

        # Establish the database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor()

            # Check if the carplate and user_id match in the vehicles table
            cursor.execute("SELECT * FROM vehicles WHERE carplate = %s AND user_id = %s", (carplate, user_id))
            vehicle = cursor.fetchone()

            if vehicle:
                # If match found, proceed to delete the carplate
                delete_query = "DELETE FROM vehicles WHERE carplate = %s AND user_id = %s"
                cursor.execute(delete_query, (carplate, user_id))
                connection.commit()

                logging.debug(f"Carplate {carplate} removed for user {user_id}")
                return jsonify({"message": "Carplate removed successfully"}), 210
            else:
                logging.debug(f"No matching record found for carplate: {carplate}, user_id: {user_id}")
                return jsonify({"message": "No matching record found for the provided carplate and user_id"}), 404

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error removing carplate", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
@app.route('/reserve', methods=['POST'])
def place_reservation():
    """API endpoint to place a new reservation"""
    try:
        # Parse the input data from the request body (JSON)
        data = request.get_json()

        # Extract necessary fields from the data
        user_id = data.get('user_id')
        slot_id = data.get('slot_id')
        reservation_start_str = data.get('reservation_start')
        reservation_end_str = data.get('reservation_end')
        location = data.get('location')  # New field for location
        status = data.get('status', 'Reserved')  # Default to 'Reserved' if not provided
        price = data.get('price')  # New field for price

        # Convert start and end times to datetime objects
        reservation_start = datetime.strptime(reservation_start_str, '%Y-%m-%d %H:%M:%S')
        reservation_end = datetime.strptime(reservation_end_str, '%Y-%m-%d %H:%M:%S')

        # Check for mandatory fields
        if not all([user_id, slot_id, reservation_start, reservation_end, location, price]):
            return jsonify({"message": "Please provide user_id, slot_id, reservation_start, reservation_end, location, and price"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor()

            # Insert the reservation into the reservations table
            insert_query = """
                INSERT INTO reservations (user_id, slot_id, reservation_start, reservation_end, location, status, price, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """
            created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')  # Current UTC time
            cursor.execute(insert_query, (user_id, slot_id, reservation_start_str, reservation_end_str, location, status, price, created_at))
            connection.commit()

            return jsonify({"message": "Reservation placed successfully"}), 201

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error placing reservation", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()




class ParkingSimulation:
    def __init__(self):
        self.G = nx.DiGraph()
        self.nodes = [1, 2, 3, 4, 5, 6, 7, 8]
        self.G.add_nodes_from(self.nodes)
        edges = [(1, 8, 4), (2, 8, 4), (3, 8, 3), (4, 8, 3), (5, 8, 2), (6, 8, 2), (7, 8, 1)]
        self.G.add_weighted_edges_from(edges)
        self.edge_usage = {(u, v): 2 for u, v in self.G.edges}
        self.edge_cooldown = {(u, v): 0 for u, v in self.G.edges}

    def dijkstra_path(self, start, end):
        queue = [(0, start, [])]
        seen = set()
        min_dist = {start: 0}

        while queue:
            (cost, node, path) = heapq.heappop(queue)
            if node in seen:
                continue

            path = path + [node]
            seen.add(node)

            if node == end:
                return (cost, path)

            for neighbor in self.G.neighbors(node):
                weight = self.G[node][neighbor]['weight']
                if neighbor not in seen:
                    prev_cost = min_dist.get(neighbor, float('inf'))
                    new_cost = cost + weight
                    if new_cost < prev_cost:
                        min_dist[neighbor] = new_cost
                        heapq.heappush(queue, (new_cost, neighbor, path))

        return float('inf'), []

    def is_edge_available(self, u, v, current_time):
        return self.edge_usage[(u, v)] > 0 and self.edge_cooldown[(u, v)] <= current_time

    def use_edge(self, u, v, current_time):
        if self.is_edge_available(u, v, current_time):
            self.edge_usage[(u, v)] -= 1
            if self.edge_usage[(u, v)] <= 0:
                self.edge_cooldown[(u, v)] = current_time + 10  # Set cooldown time to 10 seconds
                self.edge_usage[(u, v)] = 2

    def check_cooldown_reset(self, current_time):
        reset_edges = []
        for (u, v), cooldown_time in self.edge_cooldown.items():
            if cooldown_time <= current_time and cooldown_time != 0:
                self.edge_cooldown[(u, v)] = 0
                reset_edges.append((u, v))
        return reset_edges

    def get_available_slots_from_db(self):
        """Fetch the count of available slots for each zone from the database."""
        try:
            connection = create_connection()
            if connection:
                cursor = connection.cursor()
                query = """
                        SELECT zone, COUNT(*) as available_slots
                        FROM parking_slots
                        WHERE realtime_availability = 'Available' AND allow_reservation = 'false'
                        GROUP BY zone;

                """
                cursor.execute(query)
                result = cursor.fetchall()
                return {zone: available_slots for zone, available_slots in result}
        except Error as e:
            logging.error(f"Database error: {e}")
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()
        return {}

    def get_best_parking_node(self):
        current_time = time.time()
        available_slots = self.get_available_slots_from_db()

        sorted_nodes = sorted(
            [(self.dijkstra_path(node, 8)[0], node) for node in available_slots if node != 8]
        )
        return sorted_nodes

    def attempt_assign_from_best_node(self):
        current_time = time.time()
        sorted_nodes = self.get_best_parking_node()

        for cost, best_node in sorted_nodes:
            cost, path = self.dijkstra_path(best_node, 8)
            if path and self.is_edge_available(best_node, 8, current_time):
                self.use_edge(best_node, 8, current_time)
                return {
                    "success": True,
                    "message": f"Car assigned to slot from node {best_node}.",
                    "path": path,
                    "zone": best_node  # Return the zone for slot lookup
                }

        paths_on_cooldown = []
        for (u, v), cooldown_time in self.edge_cooldown.items():
            if cooldown_time > current_time:
                remaining_cooldown = cooldown_time - current_time
                paths_on_cooldown.append({
                    "from_node": u,
                    "to_node": v,
                    "remaining_cooldown_seconds": round(remaining_cooldown, 2)
                })

        return {
            "success": False,
            "message": "No suitable parking node available or paths are on cooldown.",
            "paths_on_cooldown": paths_on_cooldown
        }

def get_first_available_slot(zone):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            query = """
                SELECT slot_id FROM parking_slots
                WHERE zone = %s AND realtime_availability = 'Available' AND allow_reservation = 'false'
                LIMIT 1;
            """
            cursor.execute(query, (zone,))
            result = cursor.fetchone()
            if result:
                return result[0]
    except Error as e:
        logging.error(f"Database error: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
    return None

def update_slot_to_occupied(slot_id):
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            update_query = """
                UPDATE parking_slots
                SET realtime_availability = 'Occupied'
                WHERE slot_id = %s;
            """
            cursor.execute(update_query, (slot_id,))
            connection.commit()
            logging.debug(f"Slot {slot_id} updated to Occupied.")
    except Error as e:
        logging.error(f"Database error: {e}")
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

simulation = ParkingSimulation()
@app.route('/auto_assign', methods=['POST'])
def auto_assign():
    data = request.get_json()
    auth = data.get('auth')
    slot_id = data.get('slot_id')  # Input slot_id
    carplate = data.get('carplate')  # Input carplate
    res_id = data.get('res_id')  # Reservation ID input for Case 1

    # Validate authentication token
    if auth != "APU Carpark B":
        return jsonify({
            "success": "false",
            "message": "Unauthorized access. Invalid authentication token."
        }), 401

    # Case 1: If slot_id is provided
    if slot_id:
        try:
            connection = create_connection()
            if connection:
                cursor = connection.cursor()
                query = """
                    SELECT realtime_availability, allow_reservation, zone FROM parking_slots
                    WHERE slot_id = %s;
                """
                cursor.execute(query, (slot_id,))
                result = cursor.fetchone()

                if result:
                    availability, allow_reservation, zone = result
                    if availability == 'Available' and allow_reservation:
                        # Update slot as occupied and add carplate
                        update_query = """
                            UPDATE parking_slots
                            SET realtime_availability = 'Occupied',
                                parked_carplate = %s
                            WHERE slot_id = %s;
                        """
                        cursor.execute(update_query, (carplate, slot_id))
                        connection.commit()

                        # If res_id is provided, update reservation status
                        if res_id:
                            reservation_query = """
                                UPDATE tanzhizheng1520$ParkEase.reservations
                                SET status = 'Entered'
                                WHERE reservation_id = %s;
                            """
                            cursor.execute(reservation_query, (res_id,))
                            connection.commit()

                        return jsonify({
                            "success": "true",
                            "message": f"Car assigned to slot {slot_id} in zone {zone}.",
                            "slot_id": str(slot_id),
                            "zone": str(zone),
                            "res_id": str(res_id) if res_id else ""
                        }), 200
                    else:
                        return jsonify({
                            "success": "false",
                            "message": f"Slot {slot_id} is not available or cannot be reserved."
                        }), 400
                else:
                    return jsonify({
                        "success": "false",
                        "message": f"Slot {slot_id} does not exist."
                    }), 404
        except Error as e:
            logging.error(f"Database error: {e}")
            return jsonify({"success": "false", "message": "Database error occurred"}), 500
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()

    # Case 2: If no slot_id is provided
    result = simulation.attempt_assign_from_best_node()

    if result["success"] == True:
        zone = result.get("zone")
        slot_id = None

        try:
            connection = create_connection()
            if connection:
                cursor = connection.cursor()
                query = """
                    SELECT slot_id FROM parking_slots
                    WHERE zone = %s AND realtime_availability = 'Available' AND allow_reservation = false
                    LIMIT 1;
                """
                cursor.execute(query, (zone,))
                db_result = cursor.fetchone()
                if db_result:
                    slot_id = db_result[0]

                    # Update the slot as occupied and assign carplate
                    update_query = """
                        UPDATE parking_slots
                        SET realtime_availability = 'Occupied',
                            parked_carplate = %s
                        WHERE slot_id = %s;
                    """
                    cursor.execute(update_query, (carplate, slot_id))
                    connection.commit()

                    result["slot_id"] = str(slot_id)  # Convert slot_id to string
                    result["zone"] = str(zone)  # Convert zone to string
                    slots_left = simulation.get_available_slots_from_db().get(zone, 0)
                    result["slots_left"] = str(slots_left)  # Convert slots_left to string
                else:
                    result["success"] = "false"
                    result["message"] = f"No available slots in zone {zone} with allow_reservation = false."
                    return jsonify(result), 400
        except Error as e:
            logging.error(f"Database error: {e}")
            return jsonify({"success": "false", "message": "Database error occurred"}), 500
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()

    # Ensure all response keys are strings
    result["success"] = str(result["success"]).lower()
    result["slot_id"] = str(result.get("slot_id", ""))
    result["zone"] = str(result.get("zone", ""))
    result["slots_left"] = str(result.get("slots_left", ""))

    return jsonify(result), 200 if result["success"] == "true" else 400






@app.route('/get_reservations', methods=['GET'])
def get_reservations():
    uid = request.args.get('uid')
    logging.debug(f"Received request for reservations with uid: {uid}")

    connection = create_connection()
    if connection is None:
        logging.error("Failed to create a database connection")
        return jsonify({"error": "Could not connect to the database"}), 500

    try:
        cursor = connection.cursor(dictionary=True)

        # Update the database to mark expired reservations
        current_time = datetime.now()
        update_query = """
            UPDATE reservations
            SET status = 'Expired'
            WHERE status = 'Reserved' AND reservation_end < %s
        """
        logging.debug("Executing update query to mark expired reservations.")
        cursor.execute(update_query, (current_time,))
        connection.commit()  # Commit the update changes

        # Retrieve reservations based on user ID and sort by reservation_start descending
        if uid:
            query = "SELECT * FROM reservations WHERE user_id = %s ORDER BY reservation_start DESC"
            logging.debug(f"Executing query: {query} with uid={uid}")
            cursor.execute(query, (uid,))
        else:
            query = "SELECT * FROM reservations ORDER BY reservation_start DESC"
            logging.debug(f"Executing query: {query}")
            cursor.execute(query)

        reservations = cursor.fetchall()
        logging.debug(f"Query executed successfully, retrieved {len(reservations)} records")

        if not reservations:
            logging.info("No reservations found for the specified user_id")
            return jsonify({"message": "No reservations found for the specified user_id"}), 404

        # Processing each reservation record
        processed_reservations = []
        for i, reservation in enumerate(reservations, start=1):
            logging.debug(f"Processing reservation: {reservation}")

            try:
                # Add 'no' as a string
                reservation['no'] = str(i)

                # Ensure 'location' is included in each reservation
                reservation['location'] = reservation.get('location', 'Unknown')

                # Convert date fields and calculate duration
                for date_field in ['created_at', 'reservation_start', 'reservation_end']:
                    if isinstance(reservation[date_field], datetime):
                        date_str = reservation[date_field].strftime("%a, %d %b %Y")
                        time_str = reservation[date_field].strftime("%I:%M %p")
                    else:
                        # If it's a string, parse and format it
                        dt = datetime.strptime(reservation[date_field], "%Y-%m-%d %H:%M:%S")
                        date_str = dt.strftime("%a, %d %b %Y")
                        time_str = dt.strftime("%I:%M %p")

                    # Store date and time separately in the reservation dictionary
                    reservation[f"date_{date_field}"] = date_str
                    reservation[f"time_{date_field}"] = time_str
                    # Remove the original datetime field if not needed
                    del reservation[date_field]

                # Calculate duration between reservation_start and reservation_end
                start_dt = datetime.strptime(reservation['date_reservation_start'] + ' ' + reservation['time_reservation_start'], "%a, %d %b %Y %I:%M %p")
                end_dt = datetime.strptime(reservation['date_reservation_end'] + ' ' + reservation['time_reservation_end'], "%a, %d %b %Y %I:%M %p")
                duration = end_dt - start_dt
                hours, remainder = divmod(duration.total_seconds(), 3600)
                minutes = remainder // 60
                reservation['duration'] = f"{int(hours)} hrs {int(minutes)} mins"

                processed_reservations.append(reservation)
            except Exception as e:
                logging.error(f"Error processing reservation: {e}")
                return jsonify({"error": f"Error processing reservation: {e}"}), 500

        logging.debug("All reservations processed successfully")
        return jsonify(processed_reservations)

    except Error as e:
        logging.error(f"SQL execution error: {e}")
        return jsonify({"error": "A database error occurred"}), 500
    finally:
        try:
            cursor.close()
            connection.close()
            logging.debug("Database connection closed")
        except Exception as e:
            logging.error(f"Error closing connection: {e}")


def get_reservation_by_id(reservation_id):
    connection = create_connection()
    if not connection:
        logging.error("Failed to create a database connection")
        return None

    try:
        cursor = connection.cursor(dictionary=True)
        query = "SELECT * FROM reservations WHERE reservation_id = %s"
        cursor.execute(query, (reservation_id,))
        reservation = cursor.fetchone()
    except Error as e:
        logging.error(f"Error executing query: {e}")
        reservation = None
    finally:
        cursor.close()
        connection.close()

    return reservation

@app.route('/get_selected_reservations', methods=['GET'])
def get_selected_reservations():
    reservation_id = request.args.get('reservation_id', type=int)
    if not reservation_id:
        return jsonify({"error": "Reservation ID is required"}), 400

    reservation = get_reservation_by_id(reservation_id)  # Fetch reservation from database
    if not reservation:
        return jsonify({"error": "Reservation not found"}), 404

    # Extract datetime fields from the reservation
    created_at = reservation['created_at']
    reservation_start = reservation['reservation_start']
    reservation_end = reservation['reservation_end']

    # Calculate duration
    duration = reservation_end - reservation_start
    duration_hours, remainder = divmod(duration.total_seconds(), 3600)
    duration_minutes = remainder // 60

    # Use Malaysia time (UTC+8)
    current_datetime = datetime.utcnow() + timedelta(hours=8)

    # Determine if the booking is "open" or "close"
    booking_status = "open" if reservation_start <= current_datetime <= reservation_end else "close"

    # Format response
    response = {
        "date_created_at": created_at.strftime("%a, %d %b %Y"),
        "time_created_at": created_at.strftime("%I:%M %p"),
        "date_reservation_start": reservation_start.strftime("%a, %d %b %Y"),
        "time_reservation_start": reservation_start.strftime("%I:%M %p"),
        "date_reservation_end": reservation_end.strftime("%a, %d %b %Y"),
        "time_reservation_end": reservation_end.strftime("%I:%M %p"),
        "duration": f"{int(duration_hours)} hrs {int(duration_minutes)} mins",
        "location": reservation["location"],
        "no": "1",  # Assuming "no" refers to the sequence or unique identifier in the response
        "reservation_id": reservation["reservation_id"],
        "slot_id": reservation["slot_id"],
        "status": reservation["status"],
        "user_id": reservation["user_id"],
        "price": reservation["price"],
        "booking": booking_status
    }

    return jsonify(response)

@app.route('/cancel_reservation', methods=['POST'])
def cancel_reservation():
    """API endpoint to cancel a reservation by updating its status to 'Cancelled'."""
    try:
        # Parse the reservation_id from the request body
        data = request.get_json()
        reservation_id = data.get('reservation_id')

        # Check if reservation_id is provided
        if not reservation_id:
            return jsonify({"message": "Please provide a reservation_id"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor()

            # Update the reservation status to 'Cancelled'
            update_query = """
                UPDATE reservations
                SET status = 'Cancelled'
                WHERE reservation_id = %s AND status = 'Reserved'
            """
            cursor.execute(update_query, (reservation_id,))
            connection.commit()

            # Check if any row was affected (i.e., if reservation was 'Reserved')
            if cursor.rowcount == 0:
                return jsonify({"message": "No reservation found with status 'Reserved' for the given reservation_id"}), 404

            return jsonify({"message": "Reservation cancelled successfully"}), 200

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error cancelling reservation", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
@app.route('/list_transaction', methods=['GET'])
def list_transaction():
    """API endpoint to list all transactions for a specific user ID (uid), sorted by latest datetime."""
    try:
        # Get the uid from the query parameters
        uid = request.args.get('uid')

        # Check if uid is provided
        if not uid:
            return jsonify({"message": "Please provide a uid"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)  # Use dictionary cursor for JSON formatting

            # Query to fetch all transactions for the given uid, sorted by latest datetime
            query = "SELECT * FROM transaction WHERE uid = %s ORDER BY datetime DESC"
            cursor.execute(query, (uid,))
            transactions = cursor.fetchall()

            # If no transactions exist, return a 500 status code
            if not transactions:
                return jsonify({"message": "No transactions found for the provided uid"}), 500

            # Modify the response to include separate 'date' and 'time' (AM/PM format),
            # format the amount with "RM", and add "amount_type" only when it's "add"
            for transaction in transactions:
                if 'datetime' in transaction:
                    datetime_value = transaction.pop('datetime')
                    transaction['date'] = datetime_value.strftime('%Y-%m-%d') if datetime_value else None
                    transaction['time'] = datetime_value.strftime('%I:%M %p') if datetime_value else None  # AM/PM format

                # Add "RM" prefix to the amount and set amount_type if amount >= 0
                if 'amount' in transaction:
                    amount = transaction['amount']
                    transaction['amount'] = f"RM{abs(amount):.2f}" if amount >= 0 else f"-RM{abs(amount):.2f}"
                    if amount >= 0:
                        transaction['amount_type'] = "add"  # Set amount_type only for positive amounts
                    else:
                        transaction.pop('amount_type', None)  # Unset amount_type if present for negative amounts

            return jsonify(transactions), 200  # Return transactions directly as a JSON array

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching transactions", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


@app.route('/get_selected_transaction', methods=['GET'])
def get_transaction_by_txid():
    """API endpoint to fetch transaction details by transaction ID (txid)."""
    try:
        # Get the txid from the query parameters
        txid = request.args.get('txid')

        # Check if txid is provided
        if not txid:
            return jsonify({"message": "Please provide a txid"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)  # Use dictionary cursor for JSON formatting

            # Query to fetch the transaction details for the given txid
            query = "SELECT * FROM transaction WHERE txid = %s"
            cursor.execute(query, (txid,))
            transaction = cursor.fetchone()

            # If no transaction exists, return a 404 status
            if not transaction:
                return jsonify({"message": "Transaction not found for the provided txid"}), 404

            # Modify the response to include separate 'date' and 'time', and format the amount
            if 'datetime' in transaction:
                datetime_value = transaction.pop('datetime')
                transaction['date'] = datetime_value.strftime('%Y-%m-%d') if datetime_value else None
                transaction['time'] = datetime_value.strftime('%I:%M %p') if datetime_value else None  # AM/PM format

            if 'amount' in transaction:
                amount = transaction['amount']
                transaction['amount'] = f"RM{abs(amount):.2f}" if amount >= 0 else f"-RM{abs(amount):.2f}"
                if amount >= 0:
                    transaction['amount_type'] = "add"  # Set amount_type only for positive amounts

            return jsonify(transaction), 200

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching transaction", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()



def reset_parking_slots():
    """
    Resets all parking slots by changing realtime_availability to 'Available'
    and clearing the parked_carplate.
    """
    try:
        connection = create_connection()
        if connection:
            cursor = connection.cursor()
            # Update query to reset the parking slots
            reset_query = """
                UPDATE parking_slots
                SET realtime_availability = 'Available',
                    parked_carplate = NULL;
            """
            cursor.execute(reset_query)
            connection.commit()
            logging.info("All parking slots have been reset successfully.")
            return {
                "success": True,
                "message": "All parking slots have been reset successfully."
            }
    except Error as e:
        logging.error(f"Database error during reset: {e}")
        return {
            "success": False,
            "message": "An error occurred while resetting the parking slots."
        }
    finally:
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
def generate_record_id():
    """Generate a unique record ID based on the current timestamp."""
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')  # UTC timestamp with microseconds
    return f"PID{timestamp}"  # Format: PIDYYYYMMDDHHMMSSFFFFFF

def get_malaysia_time():
    """Get the current time in Malaysia (UTC+8)."""
    malaysia_time = datetime.utcnow() + timedelta(hours=8)
    return malaysia_time.strftime('%Y-%m-%d %H:%M:%S')

@app.route('/post_parking_record', methods=['POST'])
def post_parking_record():
    """API endpoint to handle parking record operations (add or update)."""
    try:
        # Parse input data (JSON body)
        data = request.get_json()
        case = str(data.get('case', ''))  # Convert case to string
        uid = str(data.get('uid', ''))  # Convert uid to string
        carplate = str(data.get('carplate', ''))  # Convert carplate to string
        slot_id = str(data.get('slot_id', ''))  # Convert slot_id to string
        zone = str(data.get('zone', ''))  # Convert zone to string
        datetime_res = str(data.get('datetime_res', ''))  # Convert datetime_res to string

        # Validate and fix datetime_res
        if datetime_res:
            try:
                # Try parsing the custom format (e.g., 'Fri, 29 Nov 2024 12:00 AM')
                datetime_res = datetime.strptime(datetime_res, "%a, %d %b %Y %I:%M %p").strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                try:
                    # Try parsing MySQL format (e.g., '2024-11-29 00:00:00')
                    datetime_res = datetime.strptime(datetime_res, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    return jsonify({"message": "Invalid datetime_res format. Use 'Fri, 29 Nov 2024 12:00 AM' or 'YYYY-MM-DD HH:MM:SS'"}), 400
        else:
            datetime_res = None  # Default to None if not provided

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor()

            # Case 1: Add a new parking record
            if case == "1":  # Case must match the string "1"
                # Generate record ID and Malaysia datetime_in
                record_id = generate_record_id()
                datetime_in = get_malaysia_time()

                # Insert the new parking record
                insert_query = """
                    INSERT INTO parking_record (record_id, uid, carplate, slot_id, zone, datetime_in, datetime_res)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """
                cursor.execute(insert_query, (record_id, uid, carplate, slot_id, zone, datetime_in, datetime_res))
                connection.commit()

                return jsonify({
                    "message": "Parking record added successfully",
                    "record_id": record_id,
                    "datetime_in": datetime_in,
                    "datetime_res": datetime_res  # Already a string
                }), 201

            # Case 2: Update an existing parking record
            elif case == "2":  # Case must match the string "2"
                record_id = str(data.get('record_id', ''))  # Convert record_id to string

                # Ensure required fields are provided
                if not record_id:
                    return jsonify({"message": "Please provide record_id for updating"}), 400

                # Generate Malaysia datetime_out
                datetime_out = get_malaysia_time()

                # Update the parking record
                update_query = """
                    UPDATE parking_record
                    SET datetime_out = %s, datetime_res = %s
                    WHERE record_id = %s AND uid = %s AND carplate = %s
                """
                cursor.execute(update_query, (datetime_out.strftime('%Y-%m-%d %H:%M:%S'), datetime_res, record_id, uid, carplate))
                connection.commit()

                # Check if the update affected any rows
                if cursor.rowcount == 0:
                    return jsonify({"message": "No matching record found to update"}), 404

                return jsonify({
                    "message": "Parking record updated successfully",
                    "record_id": record_id,
                    "datetime_out": datetime_out.strftime('%Y-%m-%d %H:%M:%S'),
                    "datetime_res": datetime_res  # Already a string
                }), 200

            # Invalid case
            else:
                return jsonify({"message": "Invalid case provided. Use 1 for Add or 2 for Update."}), 400

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error processing parking record", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()
@app.route('/list_parking_record', methods=['POST'])
def list_parking_record():
    """API endpoint to list all parking records for a specific user ID (uid), sorted by datetime_out (NULL first)."""
    try:
        # Parse input data
        data = request.get_json()
        uid = data.get('uid')

        # Check if uid is provided
        if not uid:
            return jsonify({"message": "Please provide a uid"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)  # Use dictionary cursor for JSON formatting

            # Query to fetch parking records sorted by datetime_out (NULL first)
            query = """
                SELECT record_id, carplate, slot_id, zone, datetime_in, datetime_out, datetime_res
                FROM parking_record
                WHERE uid = %s
                ORDER BY datetime_out IS NOT NULL, datetime_out ASC
            """
            cursor.execute(query, (uid,))
            parking_records = cursor.fetchall()

            # If no parking records exist, return a 404 status code
            if not parking_records:
                return jsonify({"message": "No parking records found for the provided uid"}), 404

            # Get the current time in Malaysia
            malaysia_timezone = pytz.timezone('Asia/Kuala_Lumpur')
            current_time = datetime.now(malaysia_timezone)

            # Process each record
            for record in parking_records:
                # Convert `datetime_in` to Malaysia timezone and remove seconds
                if record['datetime_in']:
                    if isinstance(record['datetime_in'], datetime):
                        datetime_in = malaysia_timezone.localize(record['datetime_in'])
                    else:
                        datetime_in = datetime.strptime(record['datetime_in'], '%Y-%m-%d %H:%M:%S')
                        datetime_in = malaysia_timezone.localize(datetime_in)

                    record['datetime_in'] = datetime_in.strftime('%a, %d %b %Y %I:%M %p')

                # Convert `datetime_res` to Malaysia timezone and remove seconds
                if record['datetime_res']:
                    if isinstance(record['datetime_res'], datetime):
                        datetime_res = malaysia_timezone.localize(record['datetime_res'])
                    else:
                        datetime_res = datetime.strptime(record['datetime_res'], '%Y-%m-%d %H:%M:%S')
                        datetime_res = malaysia_timezone.localize(datetime_res)

                    record['datetime_res'] = datetime_res.strftime('%a, %d %b %Y %I:%M %p')

                # Convert `datetime_out` to Malaysia timezone and remove seconds
                if record['datetime_out']:
                    if isinstance(record['datetime_out'], datetime):
                        datetime_out = malaysia_timezone.localize(record['datetime_out'])
                    else:
                        datetime_out = datetime.strptime(record['datetime_out'], '%Y-%m-%d %H:%M:%S')
                        datetime_out = malaysia_timezone.localize(datetime_out)

                    record['datetime_out'] = datetime_out.strftime('%a, %d %b %Y %I:%M %p')

                # Calculate the `count` field
                if record.get('datetime_res'):
                    # If datetime_res exists, calculate countdown
                    time_diff = datetime_res - current_time
                    if time_diff.total_seconds() > 0:
                        hours, remainder = divmod(time_diff.total_seconds(), 3600)
                        minutes = remainder // 60
                        record['count'] = f"{int(hours)} Hour{'s' if hours != 1 else ''} {int(minutes)} Minute{'s' if minutes != 1 else ''} Left"
                    else:
                        record['count'] = "Expired"
                else:
                    # If datetime_res does not exist, calculate count-up from datetime_in
                    time_diff = current_time - datetime_in
                    if time_diff.total_seconds() < 0:
                        # Reset negative values to zero
                        record['count'] = "0 Hours 0 Minutes"
                    else:
                        hours, remainder = divmod(time_diff.total_seconds(), 3600)
                        minutes = remainder // 60
                        record['count'] = f"{int(hours)} Hour{'s' if hours != 1 else ''} {int(minutes)} Minute{'s' if minutes != 1 else ''}"

            # Return parking records directly as a list
            return jsonify(parking_records), 200

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching parking records", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()


@app.route('/reset_parking', methods=['POST'])
def reset_parking():
    """
    API endpoint to reset all parking slots.
    """
    data = request.get_json()
    auth = data.get('auth')

    # Check authentication
    if auth != "APU Carpark B":
        return jsonify({"success": False, "message": "Unauthorized access."}), 401

    # Call the reset function
    result = reset_parking_slots()
    return jsonify(result), 200 if result['success'] else 500
@app.route('/get_selected_parking', methods=['GET'])
def get_selected_parking():
    """API endpoint to get details of a specific parking record by record_id."""
    try:
        # Parse input parameter
        record_id = request.args.get('record_id')  # Use GET parameter

        # Check if record_id is provided
        if not record_id:
            return jsonify({"message": "Please provide a record_id"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)  # Use dictionary cursor for JSON formatting

            # Query to fetch the parking record by record_id
            query = """
                SELECT record_id, carplate, slot_id, zone, datetime_in, datetime_out, datetime_res
                FROM parking_record
                WHERE record_id = %s
            """
            cursor.execute(query, (record_id,))
            parking_record = cursor.fetchone()

            # If no parking record is found, return a 404 status code
            if not parking_record:
                return jsonify({"message": "Parking record not found"}), 404

            # Get the current time in Malaysia
            malaysia_timezone = pytz.timezone('Asia/Kuala_Lumpur')
            current_time = datetime.now(malaysia_timezone)

            # Convert `datetime_in` to timezone-aware
            if parking_record['datetime_in']:
                datetime_in = parking_record['datetime_in']
                if isinstance(datetime_in, str):
                    datetime_in = datetime.strptime(datetime_in, '%Y-%m-%d %H:%M:%S')
                datetime_in = malaysia_timezone.localize(datetime_in)
                parking_record['datetime_in'] = datetime_in.strftime('%a, %d %b %Y %I:%M %p')

            # Convert `datetime_res` to timezone-aware
            if parking_record['datetime_res']:
                datetime_res = parking_record['datetime_res']
                if isinstance(datetime_res, str):
                    datetime_res = datetime.strptime(datetime_res, '%Y-%m-%d %H:%M:%S')
                datetime_res = malaysia_timezone.localize(datetime_res)
                parking_record['datetime_res'] = datetime_res.strftime('%a, %d %b %Y %I:%M %p')

            # Convert `datetime_out` to timezone-aware
            if parking_record['datetime_out']:
                datetime_out = parking_record['datetime_out']
                if isinstance(datetime_out, str):
                    datetime_out = datetime.strptime(datetime_out, '%Y-%m-%d %H:%M:%S')
                datetime_out = malaysia_timezone.localize(datetime_out)
                parking_record['datetime_out'] = datetime_out.strftime('%a, %d %b %Y %I:%M %p')

            # Calculate the `count` field
            if parking_record.get('datetime_res'):
                # If datetime_res exists, calculate countdown
                time_diff = datetime_res - current_time
                if time_diff.total_seconds() > 0:
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes = remainder // 60
                    parking_record['count'] = f"{int(hours)} Hour{'s' if hours != 1 else ''} {int(minutes)} Minute{'s' if minutes != 1 else ''} Left"
                else:
                    parking_record['count'] = "Expired"
            else:
                # If datetime_res does not exist, calculate count-up from datetime_in
                time_diff = current_time - datetime_in
                if time_diff.total_seconds() < 0:
                    # Reset negative values to zero
                    parking_record['count'] = "0 Hours 0 Minutes"
                else:
                    hours, remainder = divmod(time_diff.total_seconds(), 3600)
                    minutes = remainder // 60
                    parking_record['count'] = f"{int(hours)} Hour{'s' if hours != 1 else ''} {int(minutes)} Minute{'s' if minutes != 1 else ''}"

            # Debugging logs for count accuracy
            logging.debug(f"Current Time: {current_time}")
            logging.debug(f"Datetime In: {datetime_in}")
            logging.debug(f"Time Difference (seconds): {time_diff.total_seconds()}")

            # Return the parking record details
            return jsonify(parking_record), 200

    except Error as e:
        logging.error(f"Database error: {e}")
        return jsonify({"message": "Error fetching parking record", "error": str(e)}), 500

    finally:
        # Ensure the connection is closed
        if 'connection' in locals() and connection.is_connected():
            cursor.close()
            connection.close()

if __name__ == '__main__':
    logging.debug("Starting the Flask application")
    app.run(host='0.0.0.0', port=5000, debug=True)
