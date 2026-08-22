#!/usr/bin/env python3
"""Manage the two logins for the bonus tracker page.

    python tools/bonus_user.py add andy --role admin
    python tools/bonus_user.py add jess --name "Jess"
    python tools/bonus_user.py password andy
    python tools/bonus_user.py list
    python tools/bonus_user.py remove jess

Passwords are typed at the prompt (never on the command line, where they'd
land in shell history) and stored only as hashes in bonus_users.json.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from bonus.auth import (
    MIN_PASSWORD_LENGTH,
    USERS_FILE,
    add_user,
    load_users,
    remove_user,
    set_password,
)


def prompt_password():
    while True:
        password = getpass.getpass("Password: ")
        if len(password) < MIN_PASSWORD_LENGTH:
            print("Too short — at least %d characters." % MIN_PASSWORD_LENGTH)
            continue
        if password != getpass.getpass("Repeat password: "):
            print("Those didn't match. Try again.")
            continue
        return password


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="create a login")
    add.add_argument("username")
    add.add_argument("--name", help="display name shown on the page")
    add.add_argument("--role", choices=["admin", "member"], default="member",
                     help="admin can change bonus rates and mark a month paid")

    pw = sub.add_parser("password", help="change a password")
    pw.add_argument("username")

    sub.add_parser("list", help="show the logins that exist")

    rm = sub.add_parser("remove", help="delete a login")
    rm.add_argument("username")

    args = parser.parse_args()

    if args.command == "add":
        user = add_user(args.username, prompt_password(), args.name, args.role)
        print("Created %s (%s). Stored in %s" % (user["username"], user["role"], USERS_FILE))
    elif args.command == "password":
        set_password(args.username, prompt_password())
        print("Password updated for %s" % args.username.lower())
    elif args.command == "list":
        users = load_users()
        if not users:
            print("No logins yet. Create one with: python tools/bonus_user.py add <username>")
        for name, user in sorted(users.items()):
            print("%-12s %-8s %s" % (name, user.get("role", "member"), user.get("displayName", "")))
    elif args.command == "remove":
        print("Removed %s" % args.username.lower() if remove_user(args.username) else "No such user")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyboardInterrupt, EOFError) as e:
        sys.exit("\n%s" % (e or "Stopped."))
