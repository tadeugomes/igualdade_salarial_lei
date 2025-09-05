import pandas as pd
import processor
import tempfile
import os

# Load sample data
df = processor.load_input("sample_data.csv")

# Process data
aggregates = processor.process_data(df)

# Generate Excel report
with tempfile.TemporaryDirectory() as tmpdir:
    excel_path = os.path.join(tmpdir, "test_report.xlsx")
    processor.create_excel(df, aggregates, excel_path)
    
    # Check if the file was created
    if os.path.exists(excel_path):
        print(f"Excel file created successfully at: {excel_path}")
        
        # Copy the file to the current directory for inspection
        import shutil
        shutil.copy(excel_path, "test_report.xlsx")
        print("Excel file copied to current directory as 'test_report.xlsx'")
    else:
        print("Failed to create Excel file")