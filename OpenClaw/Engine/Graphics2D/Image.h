#ifndef IMAGE_H_
#define IMAGE_H_

#include <libwap.h>
#include <SDL2/SDL.h>
#include <stdint.h>
#include <vector>
#include <map>

class Image
{
public:
    Image();
    Image(SDL_Texture* pSDLTexture);
    ~Image();

    static SDL_Texture* GetTextureFromPid(WapPid* pid, SDL_Renderer* renderer);
    static Image* CreateImage(WapPid* pid, SDL_Renderer* renderer);
    static Image* CreatePcxImage(char* rawBuffer, uint32_t size, SDL_Renderer* renderer, bool useColorKey = false, SDL_Color colorKey = { 0, 0, 0, 0 });
    static Image* CreatePngImage(char* rawBuffer, uint32_t size, SDL_Renderer* renderer);
    static Image* CreateImageFromColor(SDL_Color color, int w, int h, SDL_Renderer* pRenderer);

    void PreserveCoatPixels(WapPid* pid);
    SDL_Texture* GetCoatTexture(SDL_Renderer* renderer, int slot);

    inline SDL_Texture* GetTexture() { return m_pTexture; }
    inline int GetWidth() { return m_Width; }
    inline int GetHeight() { return m_Height; }
    inline int GetOffsetX() { return m_OffsetX; }
    inline int GetOffsetY() { return m_OffsetY; }

    void SetOffset(int x, int y) { m_OffsetX = x; m_OffsetY = y; }

    SDL_Rect GetPositonRect(int32_t x, int32_t y);

private:
    bool Initialize(WapPid* pid, SDL_Renderer* renderer);
    bool Initialize(SDL_Texture* pTexture);

    std::vector<WAP_ColorRGBA> m_CoatPixels;
    std::map<int, SDL_Texture*> m_CoatTextures;
    SDL_Texture* m_pTexture;
    int m_Width;
    int m_Height;
    int m_OffsetX;
    int m_OffsetY;
};

#endif
