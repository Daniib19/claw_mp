#include "LanClient.h"
#include "../Engine/GameApp/BaseGameApp.h"
#include "../Engine/GameApp/BaseGameLogic.h"
#include "../Engine/Actor/Actor.h"
#include "../Engine/Actor/Components/RenderComponent.h"
#include "../Engine/Actor/Components/ControllerComponents/HealthComponent.h"
#include "../Engine/Actor/Components/PickupComponents/PickupComponent.h"
#include "../Engine/Scene/Scene.h"
#include "../Engine/Graphics2D/Image.h"
#include "../Engine/Events/EventMgr.h"
#include "../Engine/Events/Events.h"
#include "../Engine/Actor/Components/EnemyAI/EnemyAIComponent.h"
#include "../Engine/Actor/Components/PositionComponent.h"
#include <cstdlib>
#include <sstream>
#include <cerrno>
#if !defined(EMSCRIPTEN) && !defined(__EMSCRIPTEN__) && !defined(ANDROID) && !defined(__ANDROID__)
#ifdef _WIN32
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <sys/socket.h>
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/tcp.h>
#include <sys/wait.h>
#include <spawn.h>
extern char** environ;
#include <signal.h>
#include <unistd.h>
#endif
#endif

LanClient& LanClient::Get() { static LanClient client; return client; }
LanClient::LanClient() {
    const char* host=std::getenv("OPENCLAW_SERVER");
    const char* port=std::getenv("OPENCLAW_PORT");
    if(host && *host) Connect(host,port ? std::atoi(port):27888);
}
LanClient::~LanClient() { Leave(); }
bool LanClient::Connect(const std::string& host,int port) {
#if !defined(EMSCRIPTEN) && !defined(__EMSCRIPTEN__) && !defined(ANDROID) && !defined(__ANDROID__)
    Disconnect();
#ifdef _WIN32
    static bool initialized=false;
    if(!initialized) { WSADATA data; if(WSAStartup(MAKEWORD(2,2),&data)) return false; initialized=true; }
#endif
    sockaddr_in address{}; address.sin_family=AF_INET;
    if(port<1 || port>65535 || inet_pton(AF_INET,host.c_str(),&address.sin_addr)!=1) {
        m_Status="Enter an IPv4 address and a port from 1 to 65535."; return false;
    }
    m_Port=port; address.sin_port=htons(port);
    m_Socket=socket(AF_INET,SOCK_STREAM,0);
    if(m_Socket==-1) { m_Status="Could not open a network connection."; return false; }
    int enabled=1;
    setsockopt(m_Socket,IPPROTO_TCP,TCP_NODELAY,reinterpret_cast<const char*>(&enabled),sizeof(enabled));
#ifdef _WIN32
    u_long nonblocking=1; ioctlsocket(m_Socket,FIONBIO,&nonblocking);
#else
    fcntl(m_Socket,F_SETFL,O_NONBLOCK);
#endif
    connect(m_Socket,reinterpret_cast<sockaddr*>(&address),sizeof(address));
    m_Connecting=true; m_ConnectDeadline=SDL_GetTicks()+3000;
    m_Status="Connecting to " + host + ":" + ToStr(port) + "...";
    return true;
#else
    m_Status="LAN play requires the native desktop build."; return false;
#endif
}
bool LanClient::Host(int port) {
#if !defined(EMSCRIPTEN) && !defined(__EMSCRIPTEN__) && !defined(ANDROID) && !defined(__ANDROID__)
    if(port<1 || port>65535) { m_Status="Enter a port from 1 to 65535."; return false; }
    Leave();
    char* base=SDL_GetBasePath();
    std::string script=std::string(base ? base : "") + "../server/lan_server.py";
    SDL_free(base);
    const std::string portText=ToStr(port);
#ifdef _WIN32
    std::string command="python \"" + script + "\" --port " + portText;
    STARTUPINFOA startup{}; startup.cb=sizeof(startup); PROCESS_INFORMATION process{};
    if(!CreateProcessA(NULL,&command[0],NULL,NULL,FALSE,CREATE_NO_WINDOW,NULL,NULL,&startup,&process)) {
        m_Status="Could not start server. Install Python 3.10 or newer."; return false;
    }
    CloseHandle(process.hThread); m_ServerProcess=reinterpret_cast<intptr_t>(process.hProcess);
#else
    pid_t child=0;
    char* arguments[]={const_cast<char*>("python3"),const_cast<char*>(script.c_str()),const_cast<char*>("--port"),const_cast<char*>(portText.c_str()),NULL};
    if(posix_spawnp(&child,"python3",NULL,NULL,arguments,environ)!=0) {
        m_Status="Could not start server. Install Python 3.10 or newer."; return false;
    }
    m_ServerProcess=child;
#endif
    m_Port=port; m_HostPending=true; m_HostDeadline=SDL_GetTicks()+5000; m_NextHostAttempt=SDL_GetTicks()+100;
    m_Status="Starting cooperative server..."; return true;
#else
    m_Status="Hosting requires the native desktop build."; return false;
#endif
}
void LanClient::Leave() {
    m_HostPending=false; Disconnect();
#if !defined(EMSCRIPTEN) && !defined(__EMSCRIPTEN__) && !defined(ANDROID) && !defined(__ANDROID__)
    if(m_ServerProcess) {
#ifdef _WIN32
        TerminateProcess(reinterpret_cast<HANDLE>(m_ServerProcess),0); CloseHandle(reinterpret_cast<HANDLE>(m_ServerProcess));
#else
        kill(static_cast<pid_t>(m_ServerProcess),SIGTERM); waitpid(static_cast<pid_t>(m_ServerProcess),NULL,0);
#endif
        m_ServerProcess=0;
    }
#endif
    m_Status="Disconnected. Choose Host or Join.";
}
void LanClient::SelectCoat(int slot) {
    if(slot<0 || slot>=8) return;
    m_PreferredCoat=slot;
    if(m_Ready) Send("COAT " + ToStr(slot));
}
bool LanClient::IsRoomLeader() const {
    if(!m_Ready) return false;
    for(const auto& entry:m_Players) if(entry.first<m_Id) return false;
    return true;
}
std::vector<LanClient::PlayerInfo> LanClient::Players() const {
    std::vector<PlayerInfo> result;
    for(const auto& entry:m_Players) result.push_back({entry.first,entry.second.slot,entry.second.level,entry.first==m_Id});
    return result;
}
bool LanClient::RequestMission(int level) {
    if(m_QueuedLoad==level) { m_QueuedLoad=0; return false; }
    if(!m_Ready) return false;
    if(IsRoomLeader()) { Send("START " + ToStr(level)); m_Status="Starting mission " + ToStr(level) + "..."; }
    else m_Status="The host chooses the mission for the team.";
    return true;
}
void LanClient::Disconnect() {
#if !defined(EMSCRIPTEN) && !defined(__EMSCRIPTEN__) && !defined(ANDROID) && !defined(__ANDROID__)
    if (m_Socket != -1) {
#ifdef _WIN32
        closesocket(m_Socket);
#else
        close(m_Socket);
#endif
        LOG_WARNING("LAN connection closed. Restart the game to reconnect.");
    }
#endif
    m_Socket=-1; m_Ready=false; m_Connecting=false; m_QueuedLoad=0; m_VisiblePlayers.clear(); m_Status="Connection closed. Check the server and reconnect."; m_In.clear(); m_Out.clear(); m_Players.clear();
}
void LanClient::Send(const std::string& line) {
    if(m_Socket == -1) return;
    if(m_Out.size() + line.size() > 262144) { Disconnect(); return; }
    m_Out += line + "\n";
}
void LanClient::BeginLevel(int level) {
    m_Level=level; m_Keys.clear(); m_Actors.clear(); m_PendingPickups.clear(); m_AppliedPickups.clear();
    if (m_Socket != -1) {
        std::ostringstream out; out << "STATE " << level << " 0 0 0 -"; Send(out.str());
    }
}
void LanClient::RegisterActor(uint32_t actorId, int key) {
    m_Keys[actorId]=key; m_Actors[key]=actorId;
    auto actor=g_pApp->GetGameLogic()->VGetActor(actorId).lock();
    if(!actor || actor->GetName()=="Claw") return;
    auto health=actor->GetComponent<HealthComponent>().lock();
    if(health && health->GetHealth()>0) {
        std::ostringstream out; out << "REG " << m_Level << " " << key << " " << health->GetHealth(); Send(out.str());
    }
}
void LanClient::RegisterLoot(uint32_t parentId, uint32_t actorId, int index) {
    if(m_Keys.count(parentId) && index<64) RegisterActor(actorId,100000+m_Keys[parentId]*64+index);
}
bool LanClient::RequestDamage(uint32_t actorId, int amount) {
    if(!m_Ready || m_Applying || amount<=0 || !m_Keys.count(actorId)) return false;
    std::ostringstream out; out << "DAMAGE " << m_Level << " " << m_Keys[actorId] << " " << amount; Send(out.str()); return true;
}
bool LanClient::RequestPickup(uint32_t actorId) {
    if(!m_Ready || m_Applying || !m_Keys.count(actorId)) return false;
    auto actor=g_pApp->GetGameLogic()->VGetActor(actorId).lock();
    auto claw=g_pApp->GetGameLogic()->GetClawActor();
    auto hp=claw ? claw->GetComponent<HealthComponent>().lock() : nullptr;
    if(actor && actor->GetComponent<HealthPickupComponent>().lock() && hp && hp->HasMaxHealth()) return true;
    std::ostringstream out; out << "PICK " << m_Level << " " << m_Keys[actorId]; Send(out.str()); return true;
}
bool LanClient::RequestCheckpoint(double x,double y,bool save,int number) {
    if(!m_Ready || m_Applying) return false;
    std::ostringstream out; out << "CHECK " << m_Level << " " << x << " " << y << " " << int(save) << " " << number; Send(out.str()); return true;
}
bool LanClient::RequestFinish() {
    if(!m_Ready || m_Applying) return false;
    Send("FINISH " + ToStr(m_Level)); return true;
}
void LanClient::Receive(const std::string& line) {
    std::istringstream in(line); std::string command; in >> command;
    if(command=="WELCOME") {
        in >> m_Id >> m_Slot; m_Ready=true; m_HostPending=false;
        m_Status="Connected. Waiting for the host to start a mission.";
        if(m_PreferredCoat>=0) Send("COAT " + ToStr(m_PreferredCoat));
        LOG("LAN: connected, coat " + ToStr(m_Slot+1)); return;
    }
    if(command=="NOTICE") { std::getline(in,m_Status); return; }
    if(command=="LOAD") {
        int mission;
        if(in>>mission && mission>=1 && mission<=13) {
            m_QueuedLoad=mission;
            IEventMgr::Get()->VQueueEvent(IEventDataPtr(new EventData_Menu_LoadGame(mission,true,0)));
        }
        return;
    }
    if(command=="ERROR") { LOG_ERROR("LAN: " + line); Disconnect(); m_HostPending=false; m_Status=(line=="ERROR protocol") ? "Server version differs. Restart with the latest build.":line; return; }
    if(command=="PLAYER") {
        int id; Player sample;
        if(in >> id >> sample.slot >> sample.level >> sample.x >> sample.y >> sample.mirrored >> sample.image) {
            auto& p=m_Players[id];
            p.motion.Push(sample.x,sample.y,SDL_GetTicks(),p.level!=sample.level);
            p.slot=sample.slot; p.level=sample.level; p.x=sample.x; p.y=sample.y; p.mirrored=sample.mirrored; p.image=sample.image;
            if(id==m_Id) {
                if(m_Slot!=p.slot) LOG("LAN: coat changed to " + ToStr(p.slot+1));
                m_Slot=p.slot;
            }
        }
        return;
    }
    if(command=="LEAVE") { int id; if(in>>id) m_Players.erase(id); return; }
    int level; if(!(in>>level) || level!=m_Level) return;
    auto logic=g_pApp->GetGameLogic(); auto claw=logic->GetClawActor();
    if(!claw || logic->GetGameState()!=GameState_IngameRunning) return;
    m_Applying=true;
    if(command=="ENEMY") {
        int key; double x,y; bool mirrored; std::string image;
        int leader=m_Id;
        for(const auto& entry:m_Players) if(entry.second.level==m_Level) leader=std::min(leader,entry.first);
        if(leader!=m_Id && (in>>key>>x>>y>>mirrored>>image) && m_Actors.count(key)) {
            auto actor=logic->VGetActor(m_Actors[key]).lock();
            if(actor && actor->GetComponent<EnemyAIComponent>().lock()) {
                actor->GetPositionComponent()->SetPosition(x,y);
                logic->VGetGamePhysics()->VSetPosition(actor->GetGUID(),Point(x,y));
                auto render=actor->GetComponent<ActorRenderComponent>().lock();
                if(render && render->HasImage(image)) { render->SetImage(image); render->SetMirrored(mirrored); }
            }
        }
    } else if(command=="HEALTH" || command=="PICK") {
        int key;
        if(!(in>>key)) { m_Applying=false; return; }
        if(command=="PICK" && !m_Actors.count(key)) m_PendingPickups.insert(key);
        if(m_Actors.count(key) && (command!="PICK" || !m_AppliedPickups.count(key))) {
            auto actor=logic->VGetActor(m_Actors[key]).lock();
            if(actor && actor->GetName()!="Claw") {
                if(command=="HEALTH") {
                    int value; auto health=actor->GetComponent<HealthComponent>().lock();
                    if(in>>value && health) {
                        const int previous=health->GetHealth();
                        health->ApplyNetworkHealth(value, actor->GetPositionComponent()->GetPosition(), claw->GetGUID());
                        if(previous!=value) LOG("LAN: actor " + ToStr(key) + " health " + ToStr(previous) + " -> " + ToStr(value));
                    }
                } else {
                    for(const auto& entry:*actor->GetComponents()) {
                        auto pickup=std::dynamic_pointer_cast<PickupComponent>(entry.second);
                        if(pickup) {
                            m_AppliedPickups.insert(key);
                            auto hp=claw->GetComponent<HealthComponent>().lock();
                            if(std::dynamic_pointer_cast<HealthPickupComponent>(pickup) && hp && hp->HasMaxHealth()) {
                                IEventMgr::Get()->VQueueEvent(IEventDataPtr(new EventData_Destroy_Actor(actor->GetGUID())));
                                IEventMgr::Get()->VTriggerEvent(IEventDataPtr(new EventData_Item_Picked_Up(pickup->GetPickupType())));
                            } else pickup->VOnActorEnteredTrigger(claw.get(), FixtureType_None);
                            LOG("LAN: shared pickup " + ToStr(key));
                            break;
                        }
                    }
                }
            }
        }
    } else if(command=="CHECK") {
        double x,y; bool save; int number;
        if(in>>x>>y>>save>>number) IEventMgr::Get()->VTriggerEvent(IEventDataPtr(new EventData_Checkpoint_Reached(claw->GetGUID(),Point(x,y),save,number)));
    } else if(command=="FINISH") {
        IEventMgr::Get()->VTriggerEvent(IEventDataPtr(new EventData_Finished_Level()));
    }
    m_Applying=false;
}
void LanClient::Update(uint32_t ms) {
#if !defined(EMSCRIPTEN) && !defined(__EMSCRIPTEN__) && !defined(ANDROID) && !defined(__ANDROID__)
    const uint32_t now=SDL_GetTicks();
    if(m_HostPending && !m_Ready && !m_Connecting && int32_t(now-m_NextHostAttempt)>=0) {
        if(int32_t(now-m_HostDeadline)>=0) { m_HostPending=false; m_Status="Server could not start. Check Python and the port."; }
        else { Connect("127.0.0.1",m_Port); m_NextHostAttempt=now+150; }
    }
    if(m_Socket==-1) return;
    if(m_Connecting) {
        fd_set writable; FD_ZERO(&writable); FD_SET(m_Socket,&writable); timeval timeout{0,0};
        const int ready=select(static_cast<int>(m_Socket)+1,NULL,&writable,NULL,&timeout);
        if(ready<=0) { if(int32_t(now-m_ConnectDeadline)>=0) Disconnect(); return; }
        int error=0;
#ifdef _WIN32
        int size=sizeof(error); getsockopt(m_Socket,SOL_SOCKET,SO_ERROR,reinterpret_cast<char*>(&error),&size);
#else
        socklen_t size=sizeof(error); getsockopt(m_Socket,SOL_SOCKET,SO_ERROR,&error,&size);
#endif
        if(error) { Disconnect(); return; }
        m_Connecting=false; m_LastReceive=now;
        // Loading may register actors before connect completes. The protocol
        // greeting must precede those queued messages.
        m_Out.insert(0,"HELLO 2\n");
    }
    // A late join can receive loot pickup history before enemy death creates
    // those loot actors. Apply it after the stable loot keys become available.
    std::vector<int> available;
    for(int key:m_PendingPickups) if(m_Actors.count(key)) available.push_back(key);
    for(int key:available) {
        m_PendingPickups.erase(key);
        Receive("PICK " + ToStr(m_Level) + " " + ToStr(key));
    }
    m_Timer+=ms;
    m_EnemyTimer+=ms;
    if(m_Timer>=16 && m_Ready) {
        m_Timer%=16;
        auto logic=g_pApp->GetGameLogic(); auto claw=logic->GetClawActor();
        auto render=claw ? claw->GetComponent<ActorRenderComponent>().lock() : nullptr;
        std::ostringstream out;
        if(claw && render && logic->GetGameState()==GameState_IngameRunning) {
            auto pos=claw->GetPositionComponent()->GetPosition();
            out << "STATE " << m_Level << " " << pos.x << " " << pos.y << " " << render->IsMirrored() << " " << (render->IsVisible() ? (render->GetCurrentImageName().empty() ? "frame001":render->GetCurrentImageName()) : "-");
        } else out << "STATE 0 0 0 0 -";
        Send(out.str());
        
        int leader=m_Id;
        for(const auto& entry:m_Players) if(entry.second.level==m_Level) leader=std::min(leader,entry.first);
        if(m_EnemyTimer>=200 && leader==m_Id && claw && logic->GetGameState()==GameState_IngameRunning) {
            m_EnemyTimer=0;
            for(const auto& entry:m_Actors) {
                auto actor=logic->VGetActor(entry.second).lock();
                if(!actor || !actor->GetComponent<EnemyAIComponent>().lock()) continue;
                auto hp=actor->GetComponent<HealthComponent>().lock();
                if(!hp || hp->GetHealth()<=0) continue;
                auto arc=actor->GetComponent<ActorRenderComponent>().lock();
                if(!arc || arc->GetCurrentImageName().empty()) continue;
                auto pos=actor->GetPositionComponent()->GetPosition();
                std::ostringstream enemy;
                enemy << "ENEMY " << m_Level << " " << entry.first << " " << pos.x << " " << pos.y << " " << arc->IsMirrored() << " " << arc->GetCurrentImageName();
                Send(enemy.str());
            }
        }
    }
    if(!m_Out.empty()) {
#ifdef MSG_NOSIGNAL
        int sent=send(m_Socket,m_Out.data(),m_Out.size(),MSG_NOSIGNAL);
#else
        int sent=send(m_Socket,m_Out.data(),static_cast<int>(m_Out.size()),0);
#endif
        if(sent>0) m_Out.erase(0,sent);
        else if(sent<0) {
#ifdef _WIN32
            if(WSAGetLastError()!=WSAEWOULDBLOCK) { Disconnect(); return; }
#else
            if(errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) { Disconnect(); return; }
#endif
        }
    }
    char buffer[4096];
    // Bound network work per frame so a busy LAN cannot stall rendering.
    for(int reads=0; reads<64; ++reads) {
        int count=recv(m_Socket,buffer,sizeof(buffer),0);
        if(count==0) { Disconnect(); return; }
        if(count<0) {
#ifdef _WIN32
            if(WSAGetLastError()!=WSAEWOULDBLOCK) Disconnect();
#else
            if(errno!=EAGAIN && errno!=EWOULDBLOCK && errno!=EINTR) Disconnect();
#endif
            break;
        }
        m_LastReceive=SDL_GetTicks(); m_In.append(buffer,count);
        size_t end;
        while((end=m_In.find('\n'))!=std::string::npos) {
            std::string line=m_In.substr(0,end); m_In.erase(0,end+1); Receive(line);
            if(m_Socket==-1) return;
        }
        if(m_In.size()>512) { Disconnect(); return; }
    }
    if(SDL_GetTicks()-m_LastReceive>15000) Disconnect();
#endif
}
SDL_Texture* LanClient::CoatTexture(Image* image) {
    return m_Ready ? image->GetCoatTexture(g_pApp->GetRenderer(),m_Slot) : image->GetTexture();
}
void LanClient::RenderPlayers(Scene* scene) {
    if(!m_Ready) return;
    auto logic=g_pApp->GetGameLogic(); auto claw=logic->GetClawActor();
    if(!claw || logic->GetGameState()!=GameState_IngameRunning) return;
    auto render=claw->GetComponent<ActorRenderComponent>().lock();
    if(!render) return;
    SDL_Rect camera=scene->GetCamera()->GetCameraRect();
    for(auto& entry:m_Players) {
        auto& p=entry.second;
        if(entry.first==m_Id || p.level!=m_Level || p.image=="-") continue;
        auto image=render->GetImage(p.image).lock(); if(!image) continue;
        double x,y; p.motion.Position(SDL_GetTicks(),x,y);
        SDL_Rect rect{int(x)-image->GetWidth()/2+(p.mirrored ? -image->GetOffsetX():image->GetOffsetX())-camera.x,
            int(y)-image->GetHeight()/2+image->GetOffsetY()-camera.y,image->GetWidth(),image->GetHeight()};
        if(rect.x>=camera.w || rect.y>=camera.h || rect.x+rect.w<0 || rect.y+rect.h<0) continue;
        if(m_VisiblePlayers.insert(entry.first).second) LOG("LAN: rendering remote player " + ToStr(entry.first) + " coat " + ToStr(p.slot+1));
        auto texture=image->GetCoatTexture(scene->GetRenderer(),p.slot);
        SDL_SetTextureAlphaMod(texture,255); SDL_SetTextureColorMod(texture,255,255,255);
        SDL_RenderCopyEx(scene->GetRenderer(),texture,NULL,&rect,0,NULL,p.mirrored?SDL_FLIP_HORIZONTAL:SDL_FLIP_NONE);
    }
}
