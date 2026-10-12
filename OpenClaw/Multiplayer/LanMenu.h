#pragma once
#include <SDL2/SDL.h>
#include <SDL2/SDL_ttf.h>
#include <string>
#include <map>
class LanMenu {
public:
    explicit LanMenu(SDL_Renderer* renderer);
    ~LanMenu();
    void Open();
    void Render();
    // Returns false when Escape/Back closes the overlay.
    bool Event(SDL_Event& event);
private:
    void Action(int action);
    void Text(const std::string& text,int x,int y,SDL_Color color);
    SDL_Renderer* m_Renderer;
    TTF_Font* m_Font=nullptr;
    int m_Page=0,m_Field=0,m_Mission=1,m_Coat=0;
    bool m_SelectAll=false;
    std::string m_Address="127.0.0.1",m_Port="27888";
    struct CachedText { SDL_Texture* texture; int w,h; };
    std::map<std::string,CachedText> m_Text;
};
