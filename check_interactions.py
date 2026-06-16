import json
import os

def check_drug_interaction(drug_a, drug_b, db_path="drug_interactions.json"):
    """
    Checks if there is a known drug interaction between two drug names 
    by querying a local JSON database.

    Parameters:
        drug_a (str): Name of the first drug.
        drug_b (str): Name of the second drug.
        db_path (str): File path to the JSON interaction database.

    Returns:
        dict: A dictionary containing 'severity' and 'description' if an interaction is found.
        None: If no interaction is found or the database file cannot be read.
    """
    if not os.path.exists(db_path):
        print(f"Error: Database file not found at '{db_path}'.")
        return None

    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            interactions = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"Error reading database file: {e}")
        return None

    # Normalize inputs for case-insensitive matching and trim whitespace
    name_a = str(drug_a).strip().lower()
    name_b = str(drug_b).strip().lower()

    # Iterate through database interactions
    for item in interactions:
        db_drugs = [d.strip().lower() for d in item.get("drugs", [])]
        
        # Check if both input drugs match the interaction pair
        if name_a in db_drugs and name_b in db_drugs:
            return {
                "severity": item.get("severity", "Unknown"),
                "description": item.get("description", "No description available.")
            }

    return None

# Example Usage & Verification block
if __name__ == "__main__":
    print("--- Drug Interaction Checker ---")
    
    # Test cases
    test_pairs = [
        ("Lisinopril", "Ibuprofen"),       # Should match (Moderate)
        ("Warfarin", "Aspirin"),           # Should match (Major)
        ("Atorvastatin", "Grapefruit juice"), # Should match (Moderate)
        ("Metformin", "Albuterol"),        # No interaction in local DB
        ("albuterol", "propranolol")       # Should match (Major)
    ]

    for drug1, drug2 in test_pairs:
        result = check_drug_interaction(drug1, drug2)
        if result:
            print(f"\n[INTERACTION DETECTED] {drug1} + {drug2}")
            print(f"  Severity:    {result['severity']}")
            print(f"  Description: {result['description']}")
        else:
            print(f"\n[OK] No interaction found between {drug1} and {drug2}.")
