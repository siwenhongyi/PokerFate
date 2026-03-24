-- 时间轨容器
local P = class("Timeline")
bee.Timeline = P

function P:ctor()
    self._tracks = {}
    self._ctx = nil
end

-- 上下文，持有的数据对象
function P:setCtx(ctx)
    self._ctx = ctx
end

function P:addTrack(t)
    local t = t or bee.TimeTrack:create()
    self._tracks[#self._tracks + 1] = t
    return t
end

function P:isOver()
    for _, v in ipairs(self._tracks) do
        if not v:isOver() then
            return false
        end
    end
    return true
end

function P:update(dt)
    for _, v in ipairs(self._tracks) do
        v:update(dt, self._ctx or self)
    end
end
