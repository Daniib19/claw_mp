#include "LanMenu.h"
#include "LanClient.h"
#include "CoatColors.h"
#include "../Engine/UserInterface/UserInterface.h"
#include "../Engine/GameApp/BaseGameApp.h"
#include <cstdlib>
namespace {
const SDL_Color gold={245,204,109,255}, white={238,237,224,255}, muted={174,178,188,255};
const char* coats[]={"RED","BLUE","GREEN","PURPLE","GOLD","CYAN","PINK","WHITE"};
}
LanMenu::LanMenu(SDL_Renderer* renderer):m_Renderer(renderer) { m_Font=TTF_OpenFont("clacon.ttf",20); const char* port=std::getenv("OPENCLAW_PORT"); if(port) m_Port=port; }
LanMenu::~LanMenu() { if(m_Page==1) SDL_StopTextInput(); for(auto& entry:m_Text) SDL_DestroyTexture(entry.second.texture); if(m_Font) TTF_CloseFont(m_Font); }
void LanMenu::Open() { m_Page=LanClient::Get().Connected()?2:0; m_Coat=LanClient::Get().CoatSlot(); SDL_StopTextInput(); }
void LanMenu::Text(const std::string& text,int x,int y,SDL_Color color) {
    if(!m_Font) return;
    auto found=m_Text.find(text);
    if(found==m_Text.end()) {
        if(m_Text.size()>128) { for(auto& entry:m_Text) SDL_DestroyTexture(entry.second.texture); m_Text.clear(); }
        SDL_Surface* surface=TTF_RenderUTF8_Blended(m_Font,text.c_str(),white); if(!surface) return;
        CachedText value{SDL_CreateTextureFromSurface(m_Renderer,surface),surface->w,surface->h}; SDL_FreeSurface(surface);
        if(!value.texture) return;
        found=m_Text.insert({text,value}).first;
    }
    auto& value=found->second; SDL_Rect rect{x,y,value.w,value.h};
    SDL_SetTextureColorMod(value.texture,color.r,color.g,color.b); SDL_RenderCopy(m_Renderer,value.texture,NULL,&rect);
}
void LanMenu::Render() {
    auto& lan=LanClient::Get();
    if(lan.Connected() && m_Page!=2) { m_Page=2; SDL_StopTextInput(); }
    if(!lan.Connected() && m_Page==2) m_Page=0;
    const auto size=g_pApp->GetWindowSize();
    SDL_RenderSetScale(m_Renderer,size.x/640.0f,size.y/480.0f);
    SDL_SetRenderDrawBlendMode(m_Renderer,SDL_BLENDMODE_BLEND);
    SDL_SetRenderDrawColor(m_Renderer,18,21,31,245); SDL_Rect panel{30,20,580,440}; SDL_RenderFillRect(m_Renderer,&panel);
    SDL_SetRenderDrawColor(m_Renderer,166,116,48,255); SDL_RenderDrawRect(m_Renderer,&panel);
    Text("LAN COOPERATIVE PLAY",65,42,gold);
    Text("Original missions / up to 8 players",65,72,muted);
    if(m_Page==0) {
        Text("[H] HOST A GAME",65,125,white); Text("[J] JOIN A GAME",65,175,white);
        Text("Port: " + m_Port,65,225,muted);
        Text("Choose your coat with Left / Right",65,260,white);
    } else if(m_Page==1) {
        Text("JOIN THE HOST ON YOUR LAN",65,118,gold);
        Text(std::string(m_Field==0?"> ":"  ")+"Host IP: " + m_Address,65,166,white);
        Text(std::string(m_Field==1?"> ":"  ")+"Port: " + m_Port,65,205,white);
        Text("Tab: switch field / Enter: connect",65,245,muted);
        Text("Choose coat with Left / Right",65,275,muted);
    } else {
        const auto players=lan.Players();
        Text("CONNECTED PLAYERS: " + std::to_string(players.size()) + " / 8",65,110,gold);
        int row=142;
        for(const auto& player:players) {
            const auto color=Multiplayer::RecolorCloth({0,0,255,255},player.slot);
            SDL_SetRenderDrawColor(m_Renderer,color.r,color.g,color.b,255);
            SDL_Rect dot{65,row+4,14,14}; SDL_RenderFillRect(m_Renderer,&dot);
            Text("PLAYER " + std::to_string(player.id) + " / " + coats[player.slot] + (player.local?" (YOU)":""),90,row,white);
            row+=22;
        }
        Text("MISSION " + std::to_string(m_Mission) + " / ORIGINAL CAMPAIGN",65,330,gold);
        Text(lan.IsRoomLeader()?"Up / Down: mission / Enter: start for everyone":"Waiting for host to start the mission",65,356,white);
        Text(std::string("Left/Right: ")+coats[m_Coat]+" coat / [D] disconnect",65,382,muted);
    }
    if(m_Page!=2) Text(std::string("COAT: ")+coats[m_Coat],65,310,gold);
    std::string status=lan.Status();
    if(status.size()>52) status.resize(52);
    Text(status,50,415,muted); Text("Esc: back",470,438,gold);
}
void LanMenu::Action(int action) {
    LOG("LAN menu action " + std::to_string(action));
    auto& lan=LanClient::Get();
    if(action==0) { lan.SelectCoat(m_Coat); lan.Host(std::atoi(m_Port.c_str())); }
    else if(action==1) { m_Page=1; m_Field=0; m_SelectAll=true; SDL_StartTextInput(); }
    else if(action==2) { lan.SelectCoat(m_Coat); lan.Connect(m_Address,std::atoi(m_Port.c_str())); }
    else if(action==3) lan.RequestMission(m_Mission);
    else if(action==4) { lan.Leave(); m_Page=0; }
}
bool LanMenu::Event(SDL_Event& event) {
    if(event.type==SDL_TEXTINPUT && m_Page==1) {
        auto& field=m_Field==0?m_Address:m_Port;
        for(const char* c=event.text.text;*c;++c) if((*c>='0'&&*c<='9')||(*c=='.'&&m_Field==0)) {
            if(m_SelectAll) { field.clear(); m_SelectAll=false; }
            if(field.size()<(m_Field==0?15u:5u)) field+=*c;
        }
    } else if(event.type==SDL_KEYDOWN) {
        const auto key=event.key.keysym.sym;
        if(event.key.repeat && (key==SDLK_RETURN || key==SDLK_h || key==SDLK_j || key==SDLK_d)) return true;
        if(key==SDLK_ESCAPE) {
            SDL_StopTextInput();
            if(m_Page==1) { m_Page=0; return true; }
            return false;
        }
        if(key==SDLK_LEFT || key==SDLK_RIGHT) {
            m_Coat=(m_Coat+(key==SDLK_RIGHT?1:7))%8; LanClient::Get().SelectCoat(m_Coat);
        } else if(m_Page==0 && key==SDLK_h) Action(0);
        else if(m_Page==0 && key==SDLK_j) Action(1);
        else if(m_Page==1 && key==SDLK_TAB) { m_Field=1-m_Field; m_SelectAll=true; }
        else if(m_Page==1 && key==SDLK_a && (event.key.keysym.mod&KMOD_CTRL)) m_SelectAll=true;
        else if(m_Page==1 && key==SDLK_BACKSPACE) { auto& field=m_Field==0?m_Address:m_Port; if(m_SelectAll) { field.clear(); m_SelectAll=false; } else if(!field.empty()) field.pop_back(); }
        else if(m_Page==1 && key==SDLK_RETURN) Action(2);
        else if(m_Page==2 && key==SDLK_UP) m_Mission=m_Mission==13?1:m_Mission+1;
        else if(m_Page==2 && key==SDLK_DOWN) m_Mission=m_Mission==1?13:m_Mission-1;
        else if(m_Page==2 && key==SDLK_RETURN) Action(3);
        else if(m_Page==2 && key==SDLK_d) Action(4);
    } else if(event.type==SDL_MOUSEBUTTONDOWN && event.button.button==SDL_BUTTON_LEFT) {
        const auto size=g_pApp->GetWindowSize();
        const int x=event.button.x*640/size.x,y=event.button.y*480/size.y;
        if(x>=50 && x<=590) {
            if(m_Page==0 && y>=115 && y<=155) Action(0);
            else if(m_Page==0 && y>=165 && y<=205) Action(1);
            else if(m_Page==1 && y>=155 && y<=195) { m_Field=0; m_SelectAll=true; }
            else if(m_Page==1 && y>=196 && y<=235) { m_Field=1; m_SelectAll=true; }
            else if(m_Page==1 && y>=240 && y<=270) Action(2);
            else if(m_Page==2 && y>=330 && y<=377) Action(3);
            else if(m_Page==2 && y>=378 && y<=408) Action(4);
            else if(y>=438) { SDL_StopTextInput(); return false; }
        }
    }
    return true;
}
