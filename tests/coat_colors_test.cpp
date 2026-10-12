#include "../OpenClaw/Multiplayer/CoatColors.h"
#include <cassert>
#include <set>
using Multiplayer::CoatColor;
using Multiplayer::RecolorCloth;
int main() {
    std::set<unsigned> colors;
    for(int slot=0;slot<8;++slot) {
        auto bright=RecolorCloth({20,30,240,255},slot);
        auto dark=RecolorCloth({10,15,120,255},slot);
        colors.insert((bright.r<<16)|(bright.g<<8)|bright.b);
        assert(dark.r<=bright.r && dark.g<=bright.g && dark.b<=bright.b);
        for(CoatColor original: {CoatColor{200,130,40,255},CoatColor{30,30,30,255},CoatColor{240,240,240,255},CoatColor{20,30,240,0}}) {
            auto result=RecolorCloth(original,slot);
            assert(result.r==original.r && result.g==original.g && result.b==original.b && result.a==original.a);
        }
        assert(RecolorCloth({20,30,240,120},slot).a==120);
    }
    assert(colors.size()==8);
}
