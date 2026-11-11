
def generate_global_pid(sequence):
    """Generate a global MediTrust patient ID."""
    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError("Sequence must be an integer.")

    if sequence < 1:
        raise ValueError("Sequence must be greater than zero.")

    return f"PI{sequence:03d}"


def generate_hpid(global_pid, hospital_id, sequence):
    """Generate a hospital-specific patient ID."""
    if not isinstance(global_pid, str) or not global_pid.startswith("PI"):
        raise ValueError("Invalid global PID.")

    if not hospital_id or not hospital_id.isalnum():
        raise ValueError("Invalid hospital ID.")

    if not isinstance(sequence, int) or isinstance(sequence, bool):
        raise ValueError("Sequence must be an integer.")

    if sequence < 1:
        raise ValueError("Sequence must be greater than zero.")

    return f"{global_pid}-{hospital_id.upper()}-{sequence:03d}"


if __name__ == "__main__":
    pid = generate_global_pid(100)
    hpid = generate_hpid(pid, "KRD", 89)

    print("Global PID:", pid)
    print("Hospital ID:", "KRD")
    print("Hospital-specific HPID:", hpid)
