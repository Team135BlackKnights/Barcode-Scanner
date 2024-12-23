import os
from PIL import ImageFont
from datetime import datetime
import sqlite3 as sql
import tkinter as tk
from tkinter import messagebox, Label, Entry, Button, Toplevel, Radiobutton, StringVar, OptionMenu
from databaseMain import *
from camera import takePic
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from oauth2client.service_account import ServiceAccountCredentials
from tkinter import font
import gspread
import time

# Ensure the table is created
createTable()

#API File Path, Change this depending on your API file.
APIPath = 'C:/Users/aqazi075/Downloads/robotics-barcode-77e5db7238b4.json'

# Function to center any window on the screen
def center_window(window, width=500, height=400):
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x = (screen_width // 2) - (width // 2)
    y = (screen_height // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")

# Setup Google Sheets API
def setup_google_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(APIPath, scope)
    client = gspread.authorize(creds)
    sheet = client.open("Barcode Sheet").sheet1  # Change this to your sheet's name
    return sheet

# Authenticate Google Drive API
def setup_google_drive():
    scope = ['https://www.googleapis.com/auth/drive']
    creds = ServiceAccountCredentials.from_json_keyfile_name(APIPath, scope)
    drive_service = build('drive', 'v3', credentials=creds)
    return drive_service

# Find or create the parent folder
def get_or_create_parent_folder(drive_service, parent_folder_name):
    # Check if the parent folder exists
    response = drive_service.files().list(
        q=f"name='{parent_folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id, name)'
    ).execute()

    if len(response['files']) > 0:
        # Parent folder exists
        return response['files'][0]['id']
    else:
        # Create the parent folder
        file_metadata = {
            'name': parent_folder_name,
            'mimeType': 'application/vnd.google-apps.folder'
        }
        folder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return folder.get('id')

# Create a subfolder within an existing parent folder
def create_subfolder_if_not_exists(drive_service, subfolder_name, parent_folder_id):
    # Search for the subfolder by name within the parent folder
    response = drive_service.files().list(
        q=f"name='{subfolder_name}' and '{parent_folder_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false",
        fields='files(id, name)'
    ).execute()

    if len(response['files']) > 0:
        # Subfolder exists
        return response['files'][0]['id']
    else:
        # Subfolder does not exist; create it
        file_metadata = {
            'name': subfolder_name,
            'parents': [parent_folder_id],
            'mimeType': 'application/vnd.google-apps.folder'
        }
        subfolder = drive_service.files().create(body=file_metadata, fields='id').execute()
        return subfolder.get('id')
    
# Set file permissions to make it publicly accessible
def make_file_public(drive_service, file_id):
    permission = {
        'role': 'reader',
        'type': 'anyone'
    }
    drive_service.permissions().create(
        fileId=file_id,
        body=permission
    ).execute()

# Upload an image to a specific folder and return its view link
def upload_image_to_drive(drive_service, folder_id, file_path):
    file_name = os.path.basename(file_path)
    file_metadata = {
        'name': file_name,
        'parents': [folder_id]
    }
    media = MediaFileUpload(file_path, mimetype='image/jpeg')  # Adjust mimetype if needed

    # Upload file
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink, webContentLink'
    ).execute()

    # Make the file public
    make_file_public(drive_service, file.get('id'))

    # Get the file's webViewLink to share
    file_url = file.get('webViewLink')
    print(f"File uploaded successfully. File URL: {file_url}")
    return file_url

# Function to handle scanning the ID
def scan_id(event=None):
    """Handles the Scan ID button press or Enter key event."""
    try:
        current_id = int(id_entry.get())
        if len(str(current_id)) != 6 or current_id < 0:
            raise ValueError("Invalid length")
    except ValueError as e:
        messagebox.showerror("Error", f"Invalid ID: {str(e)}")
        return

    id_entry.delete(0, tk.END)  # Clear the ID entry box

    # Fetch name from the database
    name = getName(current_id)
    if not name:  # If name is not found, prompt to enter a new one
        ask_name_window(current_id)
    else:  # If found, proceed to attendance and photo
        open_smile_window(current_id, name)

# Function to open a window for entering a new name
def ask_name_window(current_id):
    new_window = Toplevel(root)
    new_window.title("Enter Name")
    center_window(new_window, width=300, height=200)

    # Make the new window auto-focused
    new_window.focus_force()

    Label(new_window, text="Enter your first AND last name:").pack(pady=10)
    name_entry = Entry(new_window)
    name_entry.pack()

    # Focus the entry field as soon as the window opens
    name_entry.focus()

    def save_name(event=None):
        """Handles the Save Name button press or Enter key event."""
        name = name_entry.get()
        name = name.capitalize()
        
        if name:
            writeName(current_id, name)
            new_window.destroy()
            open_smile_window(current_id, name)
        else:
            messagebox.showerror("Error", "Name cannot be empty.", parent = new_window)

    # Bind the Enter key to the save_name function
    name_entry.bind("<Return>", save_name)
    Button(new_window, text="Submit", command=save_name).pack(pady=10)

# Function to open the smile window
def open_smile_window(current_id, name):
    smile_window = Toplevel(root)
    smile_window.title("Smile!")
    center_window(smile_window, width=400, height=300)

    # Make the smile window auto-focused
    smile_window.focus_force()

    # Display the "Smile!" message immediately
    display_smile_message(smile_window)

    # After half a second, take a picture and process attendance
    smile_window.after(500, lambda: take_picture_and_record(smile_window, current_id, name))

# Function to display a styled "Smile!" message
def display_smile_message(window):
    for widget in window.winfo_children():
        widget.destroy()  # Clear existing widgets

    smile_label = Label(
        window,
        text="😊 Smile! 😊",
        font=("Helvetica", 32, "bold"),
        fg="#4CAF50",
        bg="#FFFFFF"
    )
    smile_label.pack(expand=True, fill=tk.BOTH)

# Function to take a picture and record attendance
def take_picture_and_record(window, current_id, name):
    

    # Take the picture
    now = datetime.now()
    global folder
    folder = f"images/{current_id}-{name}"
    if not os.path.isdir(folder):
        os.makedirs(folder)

    file_date = now.strftime("%I-%M-%p-%Y-%m-%d")
    global picName
    picName = f"{name}__{file_date}.jpeg"
    takePic(f"{name}__{file_date}", f"{current_id}-{name}")

    window.destroy()  # Close the smile window

    # Record attendance and push to Google Sheets
    process_attendance(current_id, name)

    

# Function to process attendance
def process_attendance(current_id, name):
    now = datetime.now()
    formatted_time = now.strftime("%I:%M %p")
    formatted_date = now.strftime("%Y-%m-%d")

    # Get sign-in or sign-out 
    action = action_var.get()
    # Get event
    event = event_var.get()

    # Checks what the event is, will put the event in the "Reason" collumn if not Internship
    # If is Internship: Check if the action is performed at the correct time and if not, asks for a reason they are late/early
    reason = None
    if event == "Internship":
        if action == "out":
            if now.hour < 18 or (now.hour == 18 and now.minute < 45):
                reason = early_sign_out()  # Ask for reason
                if reason is None:
                    return  # If no reason is provided, stop processing
            else:
                reason = None
        else:
            if now.hour > 15 or (now.hour == 15 and now.minute > 45):
                reason = late_sign_in()  # Ask for reason
                if reason is None:
                    return  # If no reason is provided, stop processing
            else:
                reason = None
    elif event == "Volunteering":
        reason = "Volunteering" 
    elif event == "Build Season":
        reason = "Build Season"
            

    full_date = f"Signed {action} at: {formatted_time}, Date: {formatted_date}"

    # Store the attendance in the database
    writeData(current_id, name, full_date, reason)

    # Push data to Google Sheets
    push_to_google(current_id, name, full_date, reason)

    # Confirm attendance recording
    messagebox.showinfo("Attendance Recorded", f"Name: {name}\n{full_date}\nReason: {reason if reason else 'N/A'}")

def push_to_google(current_id, name, attendance_record, reason):
    """Push attendance data to Google Sheets and put the images in a folder"""
    
    sheet = setup_google_sheet()
    drive = setup_google_drive()
    
     # Define parent folder, subfolder, and file to upload
    parent_folder_name = "Attendance Images"  # Name of the existing or new parent folder
    subfolder_name = f"{current_id}-{name}"  # Name of the subfolder to create within the parent folder
    file_path = f"{folder}/{picName}"   # image file path
    print(file_path)
    
     # Find or create the parent folder
    parent_folder_id = get_or_create_parent_folder(drive, parent_folder_name)

    # Create subfolder within the parent folder if it doesn't exist
    subfolder_id = create_subfolder_if_not_exists(drive, subfolder_name, parent_folder_id)

    # Upload image to the subfolder and get its URL
    file_url = upload_image_to_drive(drive, subfolder_id, file_path)

    sheet.append_row([current_id, name, attendance_record, file_path, file_url, reason])  # Append a new row with the data

def early_sign_out():
    reason_window = Toplevel(root)
    reason_window.title("Reason for Early Sign-Out")
    center_window(reason_window, width=300, height=150)

    # Make the reason window auto-focused
    reason_window.focus_force()

    Label(reason_window, text="Enter reason for early sign-out:").pack(pady=10)
    reason_entry = Entry(reason_window)
    reason_entry.pack(pady=5)

    # Focus the entry field as soon as the window opens
    reason_entry.focus()

    reason = None  # Declare reason variable

    def save_reason():
        """Handles the Save Reason button press."""
        nonlocal reason  # Use the nonlocal declaration to access the outer variable
        reason = reason_entry.get()
        if reason:
            reason_window.destroy()
        else:
            messagebox.showerror("Error", "Reason cannot be empty.", parent = reason_window)


    # Bind the Enter key to the save_reason function
    reason_entry.bind("<Return>", lambda event: save_reason())

    Button(reason_window, text="Submit", command=save_reason).pack(pady=10)
    root.wait_window(reason_window)  # Wait until the window is closed
    reason = "Early sign out: " + reason
    return reason  # Return the reason after the window is closed

def late_sign_in():
    reason_window = Toplevel(root)
    reason_window.title("Reason for Late Sign-In")
    center_window(reason_window, width=300, height=150)

    # Make the reason window auto-focused
    reason_window.focus_force()

    Label(reason_window, text="Enter reason for late sign-in:").pack(pady=10)
    reason_entry = Entry(reason_window)
    reason_entry.pack(pady=5)

    # Focus the entry field as soon as the window opens
    reason_entry.focus()

    reason = None  # Declare reason variable

    def save_reason():
        """Handles the Save Reason button press."""
        nonlocal reason  # Use the nonlocal declaration to access the outer variable
        reason = reason_entry.get()
        if reason:
            reason_window.destroy()
        else:
            messagebox.showerror("Error", "Reason cannot be empty.", parent = reason_window)


    # Bind the Enter key to the save_reason function
    reason_entry.bind("<Return>", lambda event: save_reason())

    Button(reason_window, text="Submit", command=save_reason).pack(pady=10)
    root.wait_window(reason_window)  # Wait until the window is closed
    reason = "Late Sign In: " + reason
    return reason  # Return the reason after the window is closed




# Initialize the Tkinter window
root = tk.Tk()
root.title("Attendance System")
center_window(root)

# Make the window fullscreen
root.attributes("-fullscreen", True)
# Exit fullscreen with the Escape key
root.bind("<Escape>", lambda event: root.attributes("-fullscreen", False))

# Make custom font, must be intalled on system lest it default to Ariel
font_path = "Poppins-Regular"  
tk_font_large = font.Font(family="Poppins", size=48)
tk_font_medium = font.Font(family="Poppins", size=36)
tk_font_smedium = font.Font(family="Poppins", size=28)
tk_font_small = font.Font(family="Poppins", size=18)

# Variable to hold the selected action (sign-in or sign-out)
action_var = StringVar(value="in")  # Default to "in"
# Variable to help the selected event (Internship, Volunteering, or Build Season)
event_var = StringVar(value= "Internship") # Default to "Internship"

# GUI Layout
Label(root, text="Attendance System", font=tk_font_large).pack(pady=10)

Label(root, text="Enter your ID:", font=tk_font_medium).pack(pady=5)
id_entry = Entry(root, font=tk_font_medium)
id_entry.pack(pady=5)
id_entry.bind("<Return>", lambda event: scan_id())  # Bind Enter key to scan_id function

# Dropdown menu for specific event leading to being in the lab
Label(root, text="Why are you here:", font=tk_font_small).pack(pady=5)
eventsList = ["Internship", "Volunteering", "Build Season"]
w = OptionMenu(root, event_var, *eventsList)
w.config(font=tk_font_small)
w.pack()

# Radio buttons for selecting sign-in or sign-out
Label(root, text="Select Action:", font=tk_font_small).pack(pady=5)
Radiobutton(root, text="Sign In", font=tk_font_smedium, variable=action_var, value="in").pack()
Radiobutton(root, text="Sign Out", font=tk_font_smedium, variable=action_var, value="out").pack()

# Scan ID Button
Button(root, text="Scan ID", font=tk_font_smedium, command=lambda: scan_id()).pack(pady=10)

# Start the Tkinter event loop
root.mainloop()