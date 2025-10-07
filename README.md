# MATLAB Script Execution Web App

A Flask-based web application that allows users to upload and execute MATLAB scripts (.m files) through a web interface.

## Features

- **User Authentication**: Secure registration and login system
- **File Upload**: Upload MATLAB .m files through web interface
- **Script Execution**: Execute MATLAB scripts using MATLAB Engine or Octave fallback
- **Results Management**: View execution logs, download results as ZIP files
- **Dashboard**: Monitor upload status, execution progress, and statistics
- **Security**: File validation, sandboxed execution, timeout protection

## Tech Stack

- **Backend**: Python Flask, SQLAlchemy ORM, SQLite
- **Frontend**: HTML, CSS, Bootstrap 5, JavaScript
- **Authentication**: Flask-Login with password hashing
- **MATLAB Execution**: MATLAB Engine for Python (with Octave fallback)

## Prerequisites

### Required

- Python 3.7+
- Flask and dependencies (see requirements.txt)

### Optional (for MATLAB execution)

- MATLAB with MATLAB Engine for Python
- GNU Octave (fallback option)

## Installation

1. **Clone or extract the project files**

   ```bash
   cd project-t1
   ```

2. **Create a virtual environment (recommended)**

   ```bash
   python -m venv venv

   # On Windows
   venv\Scripts\activate

   # On macOS/Linux
   source venv/bin/activate
   ```

3. **Install Python dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Install MATLAB Engine (optional but recommended)**
   If you have MATLAB installed:

   ```bash
   cd "C:\Program Files\MATLAB\R20XX\extern\engines\python"
   python setup.py install
   ```

5. **Install GNU Octave (alternative to MATLAB)**
   - Windows: Download from [Octave Website](https://www.gnu.org/software/octave/)
   - macOS: `brew install octave`
   - Linux: `sudo apt-get install octave` or equivalent

## Running the Application

### Simple Version (Recommended)

```bash
python simple_app.py
```

### Original Modular Version

```bash
python app.py
```

The application will be available at: `http://localhost:5000`

## Default Login Credentials

- **Username**: `admin`
- **Password**: `admin123`

## Usage

1. **Access the application** at `http://localhost:5000`
2. **Log in** with the default credentials or register a new account
3. **Upload a MATLAB script** (.m file) using the upload page
4. **Execute the script** by clicking the "Run" button in the dashboard
5. **Monitor progress** - the status updates automatically
6. **View results** by clicking the "View" button
7. **Download results** as a ZIP file containing outputs and logs

## Project Structure

```
project-t1/
├── simple_app.py          # Simplified single-file Flask app
├── app.py                 # Original modular Flask app
├── requirements.txt       # Python dependencies
├── sample_script.m        # Example MATLAB script for testing
├── database.db           # SQLite database (created on first run)
├── uploads/              # User uploaded .m files
├── results/              # Execution results and outputs
├── templates/            # HTML templates
│   ├── base.html
│   ├── error.html
│   ├── auth/
│   │   ├── login.html
│   │   └── register.html
│   └── dashboard/
│       ├── dashboard.html
│       ├── upload.html
│       └── result.html
├── static/              # CSS and static assets
│   └── style.css
├── models/              # Database models (original version)
├── routes/              # Route blueprints (original version)
└── utils/               # Utility functions (original version)
```

## Testing

1. Use the provided `sample_script.m` for testing
2. The script creates plots, saves data, and writes results to files
3. Check execution logs and download results to verify functionality

## Security Features

- **File Validation**: Only .m files are accepted
- **Secure Filenames**: Filenames are sanitized using Werkzeug
- **Password Hashing**: User passwords are securely hashed
- **Session Management**: Flask-Login handles user sessions
- **File Size Limits**: Maximum 16MB upload size
- **Execution Timeout**: 5-minute timeout for script execution
- **Sandboxed Execution**: Scripts run in isolated directories

## Configuration

### Environment Variables (Optional)

- `SECRET_KEY`: Flask secret key for session security
- `DATABASE_URL`: Database connection string (defaults to SQLite)

### Application Settings

Edit the configuration in `simple_app.py` or `app.py`:

- `MAX_CONTENT_LENGTH`: Maximum file upload size
- `UPLOAD_FOLDER`: Directory for uploaded files
- `RESULTS_FOLDER`: Directory for execution results

## Troubleshooting

### MATLAB Engine Issues

If MATLAB Engine fails to initialize:

1. Ensure MATLAB is properly installed
2. Verify MATLAB Engine for Python is installed
3. Check MATLAB version compatibility
4. Application will automatically fall back to Octave

### Octave Issues

If Octave execution fails:

1. Verify Octave is installed and in PATH
2. Test Octave from command line: `octave --version`
3. Check script syntax compatibility between MATLAB and Octave

### File Permission Issues

Ensure the application has write permissions for:

- `uploads/` directory
- `results/` directory
- `database.db` file

### Port Already in Use

If port 5000 is busy, modify the port in the app file:

```python
app.run(debug=True, host='0.0.0.0', port=5001)
```

## Development

### Adding New Features

- Models: Add to the main app file or create in `models/`
- Routes: Add to main app file or create in `routes/`
- Templates: Add to `templates/` directory
- Static files: Add to `static/` directory

### Database Migrations

The application uses SQLite and creates tables automatically on first run.
For production, consider using PostgreSQL or MySQL with Flask-Migrate.

## Production Deployment

1. **Use a production WSGI server** (Gunicorn, uWSGI)
2. **Set up a reverse proxy** (Nginx, Apache)
3. **Use a production database** (PostgreSQL, MySQL)
4. **Configure environment variables** for sensitive settings
5. **Set up SSL/HTTPS** for secure communication
6. **Implement proper logging** and monitoring

## License

This project is for educational/demonstration purposes.

## Support

For issues or questions, refer to the troubleshooting section above or check the application logs for detailed error information.
