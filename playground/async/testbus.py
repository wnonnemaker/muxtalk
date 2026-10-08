#both of these sub to bus
server = Server()
client1 = Client(server)
client2 = Client(server)

client1.send_command("mul 3 3")
wait(1)
result1 = client1.get_result()
print(result1)
#should be 9
result2 = client2.get_result()
print(result2)
#should be idle
