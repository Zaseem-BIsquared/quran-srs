from datetime import datetime
import re
import sqlite3
import os
import itertools
from fastmigrate.core import (
    create_db,
    run_migrations,
    _ensure_meta_table,
    _set_db_version,
)


def create_and_migrate_db(db_path):
    migrations_dir = "migrations/"
    try:
        create_db(db_path)
    except sqlite3.Error:
        # if the table is already exsist, and doesn't have meta table, create it
        _ensure_meta_table(db_path)
        _set_db_version(db_path, 1)
    success = run_migrations(db_path, migrations_dir, verbose=False)
    if not success:
        # Handle migration failure
        print("Database migration failed!")


def flatten_list(list_of_lists):
    return list(itertools.chain(*list_of_lists))


def select_all_checkbox_x_data(class_name, is_select_all="true"):
    template = """
        { 
        selectAll: SELECT_ALL_PLACEHOLDER,
        globalDropdownValue: '', // Store the global dropdown selection
        updateSelectAll() {
            const checkboxes = [...$el.querySelectorAll('.CLASS_NAME_PLACEHOLDER')];
          this.selectAll = checkboxes.length > 0 && checkboxes.every(cb => cb.checked);
        },
        toggleAll() {
          $el.querySelectorAll('.CLASS_NAME_PLACEHOLDER').forEach(cb => {
            cb.checked = this.selectAll;
          });
        },
        handleCheckboxClick(e) {
            // Handle shift+click selection
            if (e.shiftKey) {
                const checkboxes = [...$el.querySelectorAll('.CLASS_NAME_PLACEHOLDER')];
                const currentCheckboxIndex = checkboxes.indexOf(e.target);
                
                // loop through the checkboxes backwards untll we find one that is checked
                for (let i = currentCheckboxIndex; i >= 0; i--) {
                    if (i != currentCheckboxIndex && checkboxes[i].checked) {break;}
                    checkboxes[i].checked = true;
                }
            }
            this.updateSelectAll();
        },
        // this function will update the selected checkbox row with the global dropdown value
       applyGlobalValue() {
        if (!this.globalDropdownValue) {
            alert('Please select a value from the global dropdown first.');
            return;
        }
        
        // Get all checked checkboxes
        const checkedCheckboxes = [...$el.querySelectorAll('.CLASS_NAME_PLACEHOLDER:checked')];
        
        if (checkedCheckboxes.length === 0) {
            alert('Please select at least one row to apply the global value.');
            return;
        }
        
        checkedCheckboxes.forEach(checkbox => {
            const row = checkbox.closest('tr');
            const rowDropdown = row.querySelector('select'); // Adjust selector as needed    
            if (rowDropdown) {
                rowDropdown.value = this.globalDropdownValue;
            }
        });
        
    },
    // This function will update the globalDropdownValue
    updateGlobalDropdownValue(e) {
          this.globalDropdownValue = e.target.value;
    }
    }
    """

    return template.replace("CLASS_NAME_PLACEHOLDER", class_name).replace(
        "SELECT_ALL_PLACEHOLDER", is_select_all
    )


# Util function
def standardize_column(column_name):
    cleaned_column = column_name.strip().lower()
    # Replace consecutive spaces with a single underscore
    return re.sub(r"\s+", "_", cleaned_column)


def destandardize_text(text):
    # Replace underscores with spaces
    text = text.replace("_", " ")
    # Capitalize the first letter of each word
    return text.title()


def current_time(f="%Y-%m-%d %I:%M %p"):
    return datetime.now().strftime(f)


def compact_format(numbers):
    if not numbers:
        return ""

    # Remove duplicates while maintaining ascending order
    unique_numbers = sorted(set(numbers))

    result = []
    start = unique_numbers[0]
    end = unique_numbers[0]

    for num in unique_numbers[1:] + [None]:  # Add sentinel value
        if num is not None and num == end + 1:
            # Continue the current range
            end = num
        else:
            # Add the completed range to the result
            if start == end:
                result.append(str(start))
            else:
                result.append(f"{start}-{end}")

            # Start a new range (if not at the end)
            if num is not None:
                start = end = num

    return ", ".join(result)


def date_to_human_readable(date_string):

    try:
        # Parse the input date string
        input_date = datetime.strptime(date_string, "%Y-%m-%d")
    except ValueError:
        # Return the original string if it can't be parsed
        return date_string

    # Convert the date to a human-readable format
    return input_date.strftime("%b %d %a")


def backup_sqlite_db(source_db_path, backup_dir):
    # Create backup directory if it doesn't exist
    os.makedirs(backup_dir, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = current_time("%Y%m%d_%H%M%S")
    db_name = os.path.basename(source_db_path)
    backup_name = f"{os.path.splitext(db_name)[0]}_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_name)

    # Connect to source database
    source = sqlite3.connect(source_db_path)

    # Connect to destination database (will create it if it doesn't exist)
    destination = sqlite3.connect(backup_path)

    # Use SQLite's backup API to create the backup
    source.backup(destination)

    # Close connections
    source.close()
    destination.close()

    return backup_path


def set_zero_to_none(data):
    if data == 0:
        return None
    return data


def format_number(num):
    # Check if the number is effectively an integer (no meaningful decimal part)
    if num % 1 == 0:
        return int(num)

    # Round to 1 decimal place
    rounded = round(num, 1)
    return rounded
