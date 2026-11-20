
from getpass import getpass

from patient_registration import register_demo_patient


def main():
    print("=== MediTrust Patient Registration Test ===")
    print("Use fictional test data only.\n")

    full_name = input("Fictional patient name: ")
    username = input("Test username: ")
    password = getpass("Test password (minimum 12 characters): ")
    hospital_id = input(
        "Demo hospital ID (KRD, DNR, HSK, DGH, or ASK): "
    )

    try:
        result = register_demo_patient(
            full_name=full_name,
            username=username,
            password=password,
            hospital_id=hospital_id,
        )

        print("\nRegistration successful!")
        print(f"Internal patient ID: {result['patient_id']}")
        print(f"Global PID: {result['global_pid']}")
        print(f"Demo hospital: {result['hospital_id']}")
        print(f"Hospital-specific HPID: {result['hpid']}")

        print(
            "\nThis test created a database record. "
            "The password itself is not displayed."
        )

    except ValueError as error:
        print(f"\nRegistration validation error: {error}")

    except Exception as error:
        print(f"\nRegistration failed: {error}")


if __name__ == "__main__":
    main()
