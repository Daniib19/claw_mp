#pragma once
#include <cstdint>
namespace Multiplayer {
struct CoatColor { uint8_t r, g, b, a; };
inline CoatColor RecolorCloth(CoatColor pixel, int slot) {
    if (slot < 0 || slot >= 8) return pixel;
    const CoatColor coats[8] = {{220,45,55,255},{45,125,240,255},
        {50,200,100,255},{180,75,225,255},{245,180,40,255},
        {40,205,205,255},{235,110,180,255},{235,235,235,255}};
    if (pixel.a && pixel.b > 35 && pixel.b > pixel.r*1.5 && pixel.b > pixel.g*1.2) {
        const auto& target=coats[slot];
        const float shade=pixel.b/255.0f;
        pixel.r=static_cast<uint8_t>(target.r*shade);
        pixel.g=static_cast<uint8_t>(target.g*shade);
        pixel.b=static_cast<uint8_t>(target.b*shade);
    }
    return pixel;
}
}
