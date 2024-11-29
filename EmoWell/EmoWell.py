from flask import Flask, jsonify, request
import mysql.connector
from mysql.connector import Error
import logging
import bcrypt  # For secure password hashing

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# MySQL connection configuration
db_config = {
    'host': 'tanzhizheng1520.mysql.pythonanywhere-services.com',
    'user': 'tanzhizheng1520',
    'password': 're2Super',
    'database': 'tanzhizheng1520$EmoWell'
}

# Create a MySQL connection
def create_connection():
    try:
        connection = mysql.connector.connect(**db_config)
        if connection.is_connected():
            logging.debug("Connected to MySQL database")
            return connection
    except Error as e:
        logging.error(f"Error connecting to MySQL: {e}")
        return None

# Root Route
@app.route('/')
def home():
    logging.debug("Home route accessed")
    return jsonify(message="Welcome to EmoWell API!")

# Route to retrieve data from Auth table (for testing only - not for production use)
@app.route('/auth-data', methods=['GET'])
def get_auth_data():
    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id, email FROM Auth;")  # Exclude passwords for security
            result = cursor.fetchall()
            logging.debug(f"Fetched data: {result}")
            return jsonify(result)
        except Error as e:
            logging.error(f"SQL query error: {e}")
            return jsonify({"error": "Error running the SQL query"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500
# Login Route
# Login Route
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    # Check for missing email or password
    if not email or not password:
        logging.debug("Email or password missing in the request")
        return jsonify({"error": "Email and password are required"}), 400

    connection = create_connection()
    if connection:
        cursor = connection.cursor(dictionary=True)
        try:
            # Query to find the user by email
            cursor.execute("SELECT * FROM Auth WHERE email = %s", (email,))
            user = cursor.fetchone()

            if user:
                # Check if the password field exists and is not None
                if 'password' in user and user['password']:
                    try:
                        # Check password hash
                        if bcrypt.checkpw(password.encode('utf-8'), user['password'].encode('utf-8')):
                            logging.debug("Login successful for user: %s", email)
                            return jsonify({"message": "Login successful", "status": "success"}), 200
                        else:
                            logging.debug("Password mismatch for user: %s", email)
                            return jsonify({"message": "Invalid credentials", "status": "failure"}), 401
                    except ValueError:
                        # Handle invalid salt in stored password hash
                        logging.error("Invalid bcrypt salt for user: %s", email)
                        return jsonify({"message": "Invalid credentials", "status": "failure"}), 401
                else:
                    logging.error("Password hash missing or malformed for user: %s", email)
                    return jsonify({"error": "Account setup issue; please contact support."}), 500
            else:
                logging.debug("User not found: %s", email)
                return jsonify({"message": "Invalid credentials", "status": "failure"}), 401

        except Error as e:
            logging.error(f"SQL query error: {e}")
            return jsonify({"error": "Error running the SQL query"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        logging.error("Failed to connect to the database")
        return jsonify({"error": "Failed to connect to the database"}), 501

# To hash passwords before inserting into the database
def hash_password(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

# Register Route to add a new user with hashed password
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({"error": "Email and password are required"}), 400

    # Generate salt and hash the password
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), salt)

    connection = create_connection()
    if connection:
        cursor = connection.cursor()
        try:
            # Insert new user with hashed password
            cursor.execute(
                "INSERT INTO Auth (email, password) VALUES (%s, %s)",
                (email, hashed_password.decode('utf-8'))
            )
            connection.commit()
            logging.debug("User registered successfully")
            return jsonify({"message": "User registered successfully", "status": "success"}), 201
        except mysql.connector.IntegrityError:
            return jsonify({"error": "Email already exists"}), 409
        except mysql.connector.Error as e:
            logging.error(f"SQL query error: {e}")
            return jsonify({"error": "Error running the SQL query"}), 500
        finally:
            cursor.close()
            connection.close()
    else:
        return jsonify({"error": "Failed to connect to the database"}), 500




if __name__ == '__main__':
    logging.debug("Starting the Flask application")
#     app.run(host='0.0.0.0', port=5000, debug=True):