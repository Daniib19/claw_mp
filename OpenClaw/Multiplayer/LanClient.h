#pragma once
#include <map>
#include <string>
#include <set>
#include <cstdint>
#include <vector>
#include "RemoteMotion.h"
class Scene;
class Image;
struct SDL_Texture;
class LanClient {
public:
    static LanClient& Get();
    void Update(uint32_t ms);
    void BeginLevel(int level);
    void RegisterActor(uint32_t actorId, int key);
    void RegisterLoot(uint32_t parentId, uint32_t actorId, int index);
    bool RequestDamage(uint32_t actorId, int amount);
    bool RequestPickup(uint32_t actorId);
    bool RequestCheckpoint(double x, double y, bool save, int number);
    bool RequestFinish();
    void RenderPlayers(Scene* scene);
    SDL_Texture* CoatTexture(Image* image);
    bool Connected() const { return m_Ready; }
    bool Connect(const std::string& host,int port);
    bool Host(int port);
    void Leave();
    void SelectCoat(int slot);
    bool RequestMission(int level);
    bool IsRoomLeader() const;
    int CoatSlot() const { return m_Slot; }
    const std::string& Status() const { return m_Status; }
    struct PlayerInfo { int id,slot,level; bool local; };
    std::vector<PlayerInfo> Players() const;
private:
    LanClient();
    ~LanClient();
    void Send(const std::string& line);
    void Receive(const std::string& line);
    void Disconnect();
    struct Player { int slot=0, level=0; double x=0,y=0; bool mirrored=false; std::string image; Multiplayer::RemoteMotion motion; };
    intptr_t m_Socket = -1;
    bool m_Ready=false, m_Applying=false;
    int m_Id=0, m_Slot=0, m_Level=0;
    uint32_t m_Timer=0, m_EnemyTimer=0, m_LastReceive=0, m_ConnectDeadline=0;
    bool m_Connecting=false, m_HostPending=false;
    int m_Port=27888, m_PreferredCoat=-1, m_QueuedLoad=0;
    intptr_t m_ServerProcess=0;
    uint32_t m_HostDeadline=0,m_NextHostAttempt=0;
    std::string m_Status="Choose Host or Join to play on your LAN.";
    std::set<int> m_VisiblePlayers;
    std::string m_In, m_Out;
    std::map<int, Player> m_Players;
    std::map<uint32_t,int> m_Keys;
    std::map<int,uint32_t> m_Actors;
    std::set<int> m_PendingPickups, m_AppliedPickups;
};
