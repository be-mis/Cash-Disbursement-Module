from mpmath import mp

mp.dps = 100  # Start with 100 decimal places

while True:
    print(mp.pi)  # Print the value of π with the current precision
    mp.dps += 10  # Increase precision by 10 each iteration
