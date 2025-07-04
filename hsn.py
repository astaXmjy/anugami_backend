import psycopg2
import openpyxl

# Database connection parameters
DB_NAME = "anugami_db"
DB_USER = "postgres"
DB_PASSWORD = "Shishir@2405"
DB_HOST = "localhost"
DB_PORT = "5432"

# Path to your Excel file with both HSN and SAC sheets
EXCEL_FILE = "HSN_SAC.xlsx"  
HSN_SHEET = "HSN_MSTR" 
SAC_SHEET = "SAC_MSTR"

def create_tax_codes_table():
    """Create a single comprehensive table for both HSN and SAC codes"""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # Create a single table for all tax codes
        cur.execute("""
            CREATE TABLE IF NOT EXISTS tax_codes (
                id SERIAL PRIMARY KEY,
                code_type VARCHAR(5) NOT NULL, -- 'HSN' or 'SAC'
                code VARCHAR(20) NOT NULL,
                description TEXT,
                UNIQUE(code_type, code)
            );
        """)
        
        # Add indices for faster lookups
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_tax_code_type ON tax_codes(code_type);
            CREATE INDEX IF NOT EXISTS idx_tax_code ON tax_codes(code);
        """)
        
        # Commit the transaction
        conn.commit()
        print("Tax codes table created successfully!")
        
        # Close cursor
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()

def import_codes_from_excel():
    """Import HSN and SAC codes from separate Excel sheets into a single table"""
    conn = None
    try:
        # Connect to the database
        conn = psycopg2.connect(
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            host=DB_HOST,
            port=DB_PORT
        )
        cur = conn.cursor()
        
        # Load Excel workbook
        workbook = openpyxl.load_workbook(EXCEL_FILE)
        
        # Process HSN codes sheet
        if HSN_SHEET in workbook.sheetnames:
            sheet = workbook[HSN_SHEET]
            hsn_count = 0
            
            # Start from row 2 (assuming row 1 has headers)
            for row in sheet.iter_rows(min_row=2):
                hsn_code = str(row[0].value).strip() if row[0].value else ""
                description = str(row[1].value).strip() if len(row) > 1 and row[1].value else ""
                
                if hsn_code:  # Only process if code is not empty
                    try:
                        cur.execute(
                            "INSERT INTO tax_codes (code_type, code, description) VALUES (%s, %s, %s) ON CONFLICT (code_type, code) DO NOTHING",
                            ('HSN', hsn_code, description)
                        )
                        hsn_count += 1
                    except Exception as e:
                        print(f"Error importing HSN code {hsn_code}: {e}")
            
            print(f"Imported {hsn_count} HSN codes.")
        else:
            print(f"Warning: Sheet '{HSN_SHEET}' not found in Excel file.")
        
        # Process SAC codes sheet
        if SAC_SHEET in workbook.sheetnames:
            sheet = workbook[SAC_SHEET]
            sac_count = 0
            
            # Start from row 2 (assuming row 1 has headers)
            for row in sheet.iter_rows(min_row=2):
                sac_code = str(row[0].value).strip() if row[0].value else ""
                description = str(row[1].value).strip() if len(row) > 1 and row[1].value else ""
                
                if sac_code:  # Only process if code is not empty
                    try:
                        cur.execute(
                            "INSERT INTO tax_codes (code_type, code, description) VALUES (%s, %s, %s) ON CONFLICT (code_type, code) DO NOTHING",
                            ('SAC', sac_code, description)
                        )
                        sac_count += 1
                    except Exception as e:
                        print(f"Error importing SAC code {sac_code}: {e}")
            
            print(f"Imported {sac_count} SAC codes.")
        else:
            print(f"Warning: Sheet '{SAC_SHEET}' not found in Excel file.")
        
        # Commit the transaction
        conn.commit()
        print("All tax codes imported successfully!")
        
        # Close cursor
        cur.close()
    except (Exception, psycopg2.DatabaseError) as error:
        print(f"Error: {error}")
    finally:
        if conn is not None:
            conn.close()

if __name__ == "__main__":
    print("Starting tax codes import process from Excel...")
    
    # Create a single table for all tax codes
    create_tax_codes_table()
    
    # Import codes from Excel sheets
    import_codes_from_excel()
    
    print("Process completed!")