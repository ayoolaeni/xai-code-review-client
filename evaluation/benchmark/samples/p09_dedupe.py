"""Removes duplicate customer records before the monthly mailing."""


def normalise_email(email):
    """Lower-case and trim an e-mail address."""
    return email.strip().lower()


def remove_duplicates(customers, seen=[]):
    """Return the customers whose e-mail has not been seen before."""
    unique = []
    for customer in customers:
        email = normalise_email(customer["email"])
        already_present = False
        for kept in unique:
            if normalise_email(kept["email"]) == email:
                already_present = True
                break
        if not already_present and email not in seen:
            unique.append(customer)
            seen.append(email)
    return unique


def mailing_list(customers):
    """E-mail addresses for the monthly mailing, without duplicates."""
    return [normalise_email(c["email"]) for c in remove_duplicates(customers)]
