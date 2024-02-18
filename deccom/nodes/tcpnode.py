
class TCPNode(object):
    def __init__(self, ip_addr = "0.0.0.0", port = None) -> None:
        if port == None:
            port = find_open_port()
        self.port = port
        self.ip_addr = ip_addr
        print("port for node",port)
        pass

    async def listen(self):
        self.server = asyncio.start_server(print, self.ip_addr,self.port)
        await self.server.serve_forever()
