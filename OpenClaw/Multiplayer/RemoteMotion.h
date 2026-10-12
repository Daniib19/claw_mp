#pragma once
#include <algorithm>
#include <cmath>
#include <cstdint>
namespace Multiplayer {
// Predict only a short LAN jitter gap. Smooth corrections without delaying a
// whole snapshot behind the sender, and snap immediately after a teleport.
class RemoteMotion {
public:
    void Push(double x,double y,uint32_t now,bool reset=false) {
        if(!m_Valid || reset || std::hypot(x-m_X,y-m_Y)>250) {
            m_DrawX=x; m_DrawY=y; m_VX=m_VY=0; m_LastDraw=now;
        } else {
            const uint32_t dt=now-m_LastSample;
            if(dt>=4 && dt<=250) {
                m_VX=(std::max)(-1.5,(std::min)(1.5,(x-m_X)/dt));
                m_VY=(std::max)(-2.0,(std::min)(2.0,(y-m_Y)/dt));
            } else m_VX=m_VY=0;
        }
        m_X=x; m_Y=y; m_LastSample=now; m_Valid=true;
    }
    void Position(uint32_t now,double& x,double& y) {
        const double ahead=std::min<uint32_t>(now-m_LastSample,34);
        const double targetX=m_X+m_VX*ahead,targetY=m_Y+m_VY*ahead;
        const double blend=1-std::exp(-double(now-m_LastDraw)/8.0);
        m_DrawX+=(targetX-m_DrawX)*blend; m_DrawY+=(targetY-m_DrawY)*blend;
        m_LastDraw=now; x=m_DrawX; y=m_DrawY;
    }
private:
    bool m_Valid=false;
    double m_X=0,m_Y=0,m_VX=0,m_VY=0,m_DrawX=0,m_DrawY=0;
    uint32_t m_LastSample=0,m_LastDraw=0;
};
}
