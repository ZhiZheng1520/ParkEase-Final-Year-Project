from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error
import logging
from datetime import datetime  # Ensure this import exists
import time
import networkx as nx
import heapq
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



# Function to get available slots with date and time for /slotleft
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
                WHERE location = %s;
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

            # Calculate available slots for each zone
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
                WHERE location = %s AND zone = %s;
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


@app.route('/addwalletamount', methods=['POST'])
def add_wallet_amount():
    """API endpoint to add an amount to the wallet for a user"""
    try:
        # Parse input data (JSON body)
        data = request.get_json()

        # Extract user_id and amount from the request body
        user_id = data.get('user_id')
        amount_to_add = data.get('amount')

        # Check if user_id and amount are provided
        if not user_id or amount_to_add is None:
            return jsonify({"message": "Please provide both user_id and amount"}), 400

        # Establish the database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor(dictionary=True)

            # Fetch the current wallet amount for the user
            cursor.execute("SELECT wallet_amount FROM users WHERE user_id = %s", (user_id,))
            result = cursor.fetchone()

            if result:
                # Add the new amount to the existing wallet amount
                new_wallet_amount = result['wallet_amount'] + amount_to_add
                update_query = "UPDATE users SET wallet_amount = %s WHERE user_id = %s"
                cursor.execute(update_query, (new_wallet_amount, user_id))
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
        status = data.get('status', 'Reserved')  # Default to 'Reserved' if not provided

        # Convert start and end times to datetime objects
        reservation_start = datetime.strptime(reservation_start_str, '%Y-%m-%d %H:%M:%S')
        reservation_end = datetime.strptime(reservation_end_str, '%Y-%m-%d %H:%M:%S')

        # Check for mandatory fields
        if not all([user_id, slot_id, reservation_start, reservation_end]):
            return jsonify({"message": "Please provide user_id, slot_id, reservation_start, and reservation_end"}), 400

        # Establish database connection
        connection = create_connection()
        if connection:
            cursor = connection.cursor()

            # Insert the reservation into the reservations table
            insert_query = """
                INSERT INTO reservations (user_id, slot_id, reservation_start, reservation_end, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s)
            """
            created_at = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')  # Current UTC time
            cursor.execute(insert_query, (user_id, slot_id, reservation_start_str, reservation_end_str, status, created_at))
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
                    WHERE realtime_availability = 'Available'
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
                WHERE zone = %s AND realtime_availability = 'Available'
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
    slot_id = data.get('slot_id')

    # Check if the auth token is correct
    if auth != "APU Carpark B":
        return jsonify({
            "success": False,
            "message": "Unauthorized access. Invalid authentication token."
        }), 401

    # Check if a specific slot_id is provided and is not an empty string
    if slot_id:
        # Check if the specific slot_id is available
        try:
            connection = create_connection()
            if connection:
                cursor = connection.cursor()
                query = """
                    SELECT realtime_availability FROM parking_slots
                    WHERE slot_id = %s;
                """
                cursor.execute(query, (slot_id,))
                result = cursor.fetchone()

                if result and result[0] == 'Available':
                    # If the slot is available, mark it as occupied
                    update_slot_to_occupied(slot_id)
                    return jsonify({
                        "success": True,
                        "message": f"Car assigned to specified slot {slot_id}.",
                        "slot_id": slot_id
                    }), 200
                else:
                    return jsonify({
                        "success": False,
                        "message": f"Slot {slot_id} is not available."
                    }), 400
        except Error as e:
            logging.error(f"Database error: {e}")
            return jsonify({"message": "Database error occurred"}), 500
        finally:
            if 'connection' in locals() and connection.is_connected():
                cursor.close()
                connection.close()

    # If no slot_id is provided or slot_id is an empty string, proceed with automatic assignment
    result = simulation.attempt_assign_from_best_node()

    if result['success']:
        zone = result.get("zone")
        slot_id = get_first_available_slot(zone)
        if slot_id:
            update_slot_to_occupied(slot_id)
            result["slot_id"] = slot_id
            slots_left = simulation.get_available_slots_from_db().get(zone, 0)
            result["slots_left"] = slots_left
        else:
            logging.warning(f"No available slot found in zone {zone}. Please check the database.")
            result["message"] = "No available slot found in the assigned zone."
            result["success"] = False
            return jsonify(result), 400

    return jsonify(result), 200 if result['success'] else 400
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
        logging.debug(f"Executing update query to mark expired reservations.")
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








if __name__ == '__main__':
    logging.debug("Starting the Flask application")
    app.run(host='0.0.0.0', port=5000, debug=True)
