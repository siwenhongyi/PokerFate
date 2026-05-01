-- 时间轨事件类
local P = class("TimeTrack")
bee.TimeTrack = P

-- 添加一个关键 key，cb: 对应回调，可为nil
function P:addKey(dt, key, cb)
    local d = {t = dt, k = key, f = cb}
    if not self._evts then
        self._evts = {d}
        self._index = 0
    else
        for i = 1, #self._evts do
            if self._evts[i].t > d.t then
                table.insert(self._evts, i, d)
                return
            end
        end
        self._evts[#self._evts + 1] = d
    end
end

-- 事件 key 被触发，子类实现
function P:onEvent(key, ctx)

end

function P:isOver()
    if self._isOver then return true end
    if self._index and self._evts then
        self._isOver = self._index >= #self._evts
        return self._isOver
    end
    self._isOver = true
    return true
end

function P:update(dt, ctx)
    if self._isOver then return end
    if not self.et then
        self.et = dt
    else
        self.et = self.et + dt
    end
    if self._index and self._evts then
        for i = self._index + 1, #self._evts do
            if self._evts[i].t <= self.et then
                self._index = i
                if self._evts[i].cb then
                    self._evts[i].cb(self._evts[i].k, ctx)
                end
                self:onEvent(self._evts[i].k, ctx)
            end
        end
    end
end