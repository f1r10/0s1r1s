from TikTokLive import TikTokLiveClient
from TikTokLive.events import ConnectEvent, CommentEvent, DisconnectEvent
 
# Client yaradılır — unique_id MƏCBURİ parametrdir
client = TikTokLiveClient(unique_id='@asi_live1')
 
# Dekorator ilə hadisəyə qulaq asırıq
@client.on(ConnectEvent)
async def baglandiqda(event: ConnectEvent):
    print(f'✅ Bağlandı! Yayımçı: @{event.unique_id}')
    print(f'   Otaq ID: {client.room_id}')
 
@client.on(CommentEvent)
async def serh_geldi(event: CommentEvent):
    # event.user.nickname → şərh edənin görünən adı
    # event.comment       → şərhin mətni
    print(f'💬 {event.user.nickname}: {event.comment}')
 
@client.on(DisconnectEvent)
async def ayrildi(event: DisconnectEvent):
    print('❌ Bağlantı kəsildi.')
 
# client.run() → bağlanır VƏ əsas axını bloklayır
client.run()
