"""Debug script to test scoped service behavior."""

from dipy import ApplicationBuilder
from abc import ABC, abstractmethod


class IConnection(ABC):
    @abstractmethod
    def close(self):
        pass


class Connection(IConnection):
    closed_count = 0
    
    def __init__(self):
        self.instance_id = id(self)
        print(f"Creating Connection {self.instance_id}")
    
    def close(self):
        Connection.closed_count += 1
        print(f"Closing Connection {self.instance_id}, total closed: {Connection.closed_count}")


class Service:
    def __init__(self, conn: IConnection):
        self.conn = conn
        print(f"Creating Service with Connection {conn.instance_id}")
    
    def do_work(self):
        return "work done"


# Setup
builder = ApplicationBuilder()
builder.services.add_scoped(IConnection, Connection)
builder.services.add_scoped(Service)

provider = builder.build()

# Test
print("\n=== Test 1 ===")
with provider.get_service(Service) as svc:
    result = svc.do_work()
    print(f"Result: {result}")

print(f"\nTotal connections closed: {Connection.closed_count}")
print(f"Expected: 1\n")

# Reset
Connection.closed_count = 0

# Test multiple scopes
print("=== Test 2: Multiple Scopes ===")
for i in range(3):
    print(f"\nScope {i}:")
    with provider.get_service(Service) as svc:
        result = svc.do_work()

print(f"\nTotal connections closed: {Connection.closed_count}")
print(f"Expected: 3")
