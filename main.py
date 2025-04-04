from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from database import get_db_connection
import traceback
from fastapi.middleware.cors import CORSMiddleware
from auth import hash_password, verify_password, create_access_token, get_current_user
from auth import get_current_user
# Function to create tables if they don't exist
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(50) NOT NULL
            )
        """)
        conn.commit()
        print("Tables created successfully")
    except Exception as e:
        print("Error creating tables:", e)
    finally:
        cur.close()
        conn.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("Starting up the application...")
    create_tables()
    yield
    print("Shutting down the application...")

app = FastAPI(lifespan=lifespan)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# User models
class UserCreate(BaseModel):
    username: str
    password_hash: str  # Changed back to password_hash
    role: str

class UserLogin(BaseModel):
    username: str
    password: str

# Home route
@app.get("/")
def read_root():
    return {"message": "Welcome to the Inventory Management System"}

# Database test endpoint
@app.get("/test-db/")
def test_db():
    try:
        conn = get_db_connection()
        conn.close()
        return {"status": "success", "message": "Database connected successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@app.post("/register/")
def register_user(user: UserCreate):
    conn = None
    try:
        # Create connection
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if username exists
        cur.execute("SELECT id FROM users WHERE username = %s", (user.username,))
        if cur.fetchone():
            raise HTTPException(status_code=400, detail="Username already exists")

        # Hash the password
        hashed_password = hash_password(user.password_hash)

        # Insert user - simplified approach
        cur.execute(
            "INSERT INTO users (username, password_hash, role) VALUES (%s, %s, %s)",
            (user.username, hashed_password, user.role)
        )
        
        # Commit the transaction
        conn.commit()
        
        # Success response without trying to get the ID
        return {"message": "User registered successfully"}
        
    except HTTPException as he:
        # Re-raise HTTP exceptions
        raise he
    except Exception as e:
        # Roll back on error
        if conn:
            conn.rollback()
        print("Registration error:", str(e))
        print("Traceback:", traceback.format_exc())
        raise HTTPException(status_code=500, detail="Registration failed. Please try again.")
    finally:
        # Close resources
        if conn:
            conn.close()

# User Login API
@app.post("/login/")
def login(user: UserLogin):
    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Fetch user from database
        cur.execute("SELECT id, username, password_hash, role FROM users WHERE username = %s", (user.username,))
        db_user = cur.fetchone()
        print("Fetched from DB:", db_user) 

        if not db_user:
            raise HTTPException(status_code=400, detail="User not found")

        user_id = db_user["id"]
        username = db_user["username"]
        hashed_password = db_user["password_hash"]
        role = db_user["role"]


        # Debugging statements
        print("Fetched Hashed Password from DB:", hashed_password)  
        print("Plain Password:", user.password)  
        print("Verification Result:", verify_password(user.password, hashed_password))  

        # Verify password
        if not verify_password(user.password, hashed_password):
            raise HTTPException(status_code=400, detail="Invalid password")

        # Generate JWT Token
        token_data = {"sub": username, "role": role}
        access_token = create_access_token(token_data)

        return {"access_token": access_token, "token_type": "bearer"}

    except Exception as e:
        print("Error during login:", str(e))  # Debugging error
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")

    finally:
        cur.close()
        conn.close()

# Protected route example
@app.get("/profile/")
def read_profile(user: dict = Depends(get_current_user)):
    return {"message": f"Hello, {user['sub']}! You are logged in as {user['role']}."}

# ========== LAB SECTION ENDPOINTS ==========

# Pydantic models for Lab Section
class LabCreate(BaseModel):
    name: str

class ComputerCreate(BaseModel):
    code: str

# Create a new lab
@app.post("/labs/")
def create_lab(lab: LabCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO labs (name) VALUES (%s) RETURNING id", (lab.name,))
        lab_id = cur.fetchone()["id"]
        conn.commit()
        return {"message": "Lab created successfully", "lab_id": lab_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get all labs
@app.get("/labs/")
def get_labs():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM labs")
        labs = cur.fetchall()
        return {"labs": labs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Delete a lab
@app.delete("/labs/{lab_id}")
def delete_lab(lab_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM labs WHERE id = %s", (lab_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Lab not found")
        conn.commit()
        return {"message": "Lab deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Add a computer to a lab
@app.post("/labs/{lab_id}/computers/")
def add_computer(lab_id: int, computer: ComputerCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("INSERT INTO computers (lab_id, code) VALUES (%s, %s) RETURNING id", (lab_id, computer.code))
        computer_id = cur.fetchone()["id"]
        conn.commit()
        return {"message": "Computer added successfully", "computer_id": computer_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get all computers in a specific lab
@app.get("/labs/{lab_id}/computers/")
def get_computers(lab_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM computers WHERE lab_id = %s", (lab_id,))
        computers = cur.fetchall()
        return {"computers": computers}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Delete a computer
@app.delete("/computers/{computer_id}")
def delete_computer(computer_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM computers WHERE id = %s", (computer_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Computer not found")
        conn.commit()
        return {"message": "Computer deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()
# Model for updating computer condition
class ComputerConditionUpdate(BaseModel):
    working_condition: bool

# Update a computer's working condition
@app.patch("/computers/{computer_id}/condition")
def update_computer_condition(computer_id: int, update: ComputerConditionUpdate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE computers SET working_condition = %s WHERE id = %s",
            (update.working_condition, computer_id)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Computer not found")
        conn.commit()
        return {"message": "Computer condition updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()
def create_tables():
        conn = get_db_connection()
        cur = conn.cursor()
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS software (
                    id SERIAL PRIMARY KEY,
                    computer_id INT REFERENCES computers(id) ON DELETE CASCADE,
                    name VARCHAR(255) NOT NULL
                )
            """)
            conn.commit()
            print("Software table created successfully")
        except Exception as e:
            print("Error creating software table:", e)
        finally:
            cur.close()
            conn.close()
class SoftwareCreate(BaseModel):
    name: str

@app.post("/computers/{computer_id}/software/")
def add_software(computer_id: int, software: SoftwareCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO software (computer_id, name) VALUES (%s, %s) RETURNING id",
            (computer_id, software.name)
        )
        software_id = cur.fetchone()["id"]
        conn.commit()
        return {"message": "Software added successfully", "software_id": software_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()
@app.get("/computers/{computer_id}/software/")
def get_software(computer_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM software WHERE computer_id = %s", (computer_id,))
        software_list = cur.fetchall()
        return {"software": software_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()
@app.delete("/software/{software_id}")
def delete_software(software_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM software WHERE id = %s", (software_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Software not found")
        conn.commit()
        return {"message": "Software deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()
from typing import Optional

# Add this to your create_tables function
def create_tables():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Your existing table creation code...
        
        # Add inventory table creation
        cur.execute("""
            CREATE TABLE IF NOT EXISTS inventory_items (
                id SERIAL PRIMARY KEY,
                item_name VARCHAR(255) NOT NULL,
                current_stock INT NOT NULL,
                threshold_stock INT NOT NULL,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()
        print("Tables created successfully including inventory_items")
    except Exception as e:
        print("Error creating tables:", e)
    finally:
        cur.close()
        conn.close()

# Pydantic models for inventory items
class InventoryItemCreate(BaseModel):
    item_name: str
    current_stock: int
    threshold_stock: int

class InventoryItemUpdate(BaseModel):
    item_name: Optional[str] = None
    current_stock: Optional[int] = None
    threshold_stock: Optional[int] = None

# Add a new inventory item
@app.post("/inventory/")
def add_inventory_item(item: InventoryItemCreate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO inventory_items (item_name, current_stock, threshold_stock) VALUES (%s, %s, %s) RETURNING id",
            (item.item_name, item.current_stock, item.threshold_stock)
        )
        item_id = cur.fetchone()["id"]
        conn.commit()
        
        # Check if alert needs to be triggered
        if item.current_stock <= item.threshold_stock:
            return {
                "message": "Inventory item added successfully", 
                "item_id": item_id,
                "alert": f"ALERT: {item.item_name} is below or at threshold stock level!"
            }
        
        return {"message": "Inventory item added successfully", "item_id": item_id}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get all inventory items
@app.get("/inventory/")
def get_inventory_items():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM inventory_items")
        items = cur.fetchall()
        return {"inventory_items": items}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get low stock alerts
@app.get("/inventory/alerts/")
def get_inventory_alerts():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM inventory_items WHERE current_stock <= threshold_stock")
        low_stock_items = cur.fetchall()
        
        alerts = []
        for item in low_stock_items:
            alerts.append({
                "item_id": item["id"],
                "item_name": item["item_name"],
                "current_stock": item["current_stock"],
                "threshold_stock": item["threshold_stock"],
                "alert_message": f"ALERT: {item['item_name']} is below or at threshold stock level!"
            })
            
        return {"alerts": alerts, "alert_count": len(alerts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Get a specific inventory item
@app.get("/inventory/{item_id}")
def get_inventory_item(item_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT * FROM inventory_items WHERE id = %s", (item_id,))
        item = cur.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        return {"inventory_item": item}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Update an inventory item
@app.put("/inventory/{item_id}")
def update_inventory_item(item_id: int, item_update: InventoryItemUpdate):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current item data
        cur.execute("SELECT * FROM inventory_items WHERE id = %s", (item_id,))
        current_item = cur.fetchone()
        if not current_item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        
        # Update only the fields that are provided
        update_values = {}
        if item_update.item_name is not None:
            update_values["item_name"] = item_update.item_name
        if item_update.current_stock is not None:
            update_values["current_stock"] = item_update.current_stock
        if item_update.threshold_stock is not None:
            update_values["threshold_stock"] = item_update.threshold_stock
        
        if not update_values:
            return {"message": "No updates provided"}
        
        # Build update query dynamically
        update_query = "UPDATE inventory_items SET "
        update_items = []
        values = []
        
        for key, value in update_values.items():
            update_items.append(f"{key} = %s")
            values.append(value)
        
        update_query += ", ".join(update_items)
        update_query += ", last_updated = CURRENT_TIMESTAMP WHERE id = %s"
        values.append(item_id)
        
        cur.execute(update_query, tuple(values))
        conn.commit()
        
        # Check if alert needs to be triggered after update
        current_stock = update_values.get("current_stock", current_item["current_stock"])
        threshold_stock = update_values.get("threshold_stock", current_item["threshold_stock"])
        item_name = update_values.get("item_name", current_item["item_name"])
        
        if current_stock <= threshold_stock:
            return {
                "message": "Inventory item updated successfully",
                "alert": f"ALERT: {item_name} is below or at threshold stock level!"
            }
        
        return {"message": "Inventory item updated successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Delete an inventory item
@app.delete("/inventory/{item_id}")
def delete_inventory_item(item_id: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("DELETE FROM inventory_items WHERE id = %s", (item_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        conn.commit()
        return {"message": "Inventory item deleted successfully"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

# Adjust inventory stock (increment or decrement)
@app.patch("/inventory/{item_id}/adjust")
def adjust_inventory_stock(item_id: int, adjustment: int):
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Get current stock
        cur.execute("SELECT * FROM inventory_items WHERE id = %s", (item_id,))
        item = cur.fetchone()
        if not item:
            raise HTTPException(status_code=404, detail="Inventory item not found")
        
        # Update stock
        new_stock = item["current_stock"] + adjustment
        if new_stock < 0:
            raise HTTPException(status_code=400, detail="Stock cannot be negative")
            
        cur.execute(
            "UPDATE inventory_items SET current_stock = %s, last_updated = CURRENT_TIMESTAMP WHERE id = %s",
            (new_stock, item_id)
        )
        conn.commit()
        
        # Check if alert needs to be triggered
        if new_stock <= item["threshold_stock"]:
            return {
                "message": f"Stock adjusted successfully. New stock: {new_stock}",
                "alert": f"ALERT: {item['item_name']} is below or at threshold stock level!"
            }
        
        return {"message": f"Stock adjusted successfully. New stock: {new_stock}"}
    except Exception as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Database Error: {str(e)}")
    finally:
        cur.close()
        conn.close()

