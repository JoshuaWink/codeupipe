"""
Demonstration of Payload.get() with Default Values
"""

from codeupipe.core import Payload, MutablePayload


def main():
    print("=" * 60)
    print("Payload.get() Default Parameter Demo")
    print("=" * 60)

    p = Payload({
        "user_name": "Alice",
        "timeout": 30,
        "retries": 3,
        "enabled": True
    })

    print("\n1. Basic Usage - Existing Keys")
    print(f"user_name (exists): {p.get('user_name', 'Anonymous')}")
    print(f"timeout (exists): {p.get('timeout', 60)}")

    print("\n2. Default Values - Missing Keys")
    print(f"page_size (missing): {p.get('page_size', 10)}")
    print(f"theme (missing): {p.get('theme', 'light')}")

    print("\n3. Working with Falsy Values")
    falsy = Payload({"zero": 0, "false": False, "empty_string": "", "empty_list": []})
    print(f"zero (0): {falsy.get('zero', 999)}")
    print(f"false (False): {falsy.get('false', True)}")
    print(f"empty_string (''): '{falsy.get('empty_string', 'default')}'")

    print("\n4. MutablePayload with Defaults")
    mutable = MutablePayload({"counter": 10})
    print(f"counter (exists): {mutable.get('counter', 0)}")
    print(f"max (missing): {mutable.get('max', 100)}")
    mutable.set('max', 50)
    print(f"max (after set): {mutable.get('max', 100)}")

    print("\n" + "=" * 60)
    print("Demo Complete!")


if __name__ == "__main__":
    main()
