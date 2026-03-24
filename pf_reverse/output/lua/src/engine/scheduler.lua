local P = {
    _timers = {},    --定时器列表 {tag: tag, dt: dt, et: et, cb: cb, num: 1}
    _tag = 0,
    _updater = {},  -- update 函数列表
    _fixer = {},    -- fixedUpdate 函数列表
    timeSpend = 0,--已经花费的时间
    timeMillisecond=0,
    dt = 0,
}
scheduler = P

function P:millisecond()
    return math.ceil(P.timeMillisecond)
end

function P:clear()
    self._timers = {}
    self._tmpAdd = {}
end

-- 执行一次延时方法
function P:once(dt, cb, target)
    local d = {tag = self:tag(), dt = dt, et = dt or -1, cb = cb, t = target, num = 1}
    self:_addTimer(d)
    return d.tag
end

-- 间隔 dt 重复执行 num 次
function P:repeatN(num, dt, cb, target)
    local d = {tag = self:tag(), dt = dt, et = dt or -1, cb = cb, t = target, num = num}
    self:_addTimer(d)
    return d.tag
end

-- 执行循环定时器
function P:schedule(dt, cb, target)
    local d = {tag = self:tag(), dt = dt, et = dt or -1, cb = cb, t = target}
    self:_addTimer(d)
    return d.tag
end

function P:removeTag(tag)
    for _, v in pairs(self._timers) do
        if v.tag == tag then
            v.remove = true
            return
        end
    end
    if self._tmpAdd then
        for k, v in ipairs(self._tmpAdd) do
            if v.tag == tag then
                table.remove(self._tmpAdd, k)
                return
            end
        end
    end
end

function P:removeTarget(target)
    for _, v in pairs(self._timers) do
        if v.t == target then
            v.remove = true
        end
    end
    if self._tmpAdd then
        for i = #self._tmpAdd, 1, -1 do
            if self._tmpAdd[i].t == target then
                table.remove(self._tmpAdd, i)
            end
        end
    end
end

function P:tag()
    self._tag = self._tag + 1
    return self._tag
end

function P:onUpdate(dt)
    -- print("==== scheduler.onUpdate", dt)
    self.dt = dt
    self.timeSpend=self.timeSpend+dt
    self._running = true
    for _, v in pairs(self._timers) do
        if not v.remove then
            if -1 == v.et then
                v.et = 0
            else
                v.et = v.et - dt
            end
            if v.et <= 0 then
                if v.num then
                    v.num = v.num - 1
                    if v.num <= 0 then
                        v.remove = true
                    end
                end
                if v.t and bee.isNull(v.t) then
                    v.remove = true
                else
                    v.cb(dt, v)
                end
                if not v.remove then
                    v.et = v.et + v.dt
                end
            end
        end
    end
    self._running = false
    for i = #self._timers, 1, -1 do
        if self._timers[i].remove then
            table.remove(self._timers, i)
        end
    end
    if self._tmpAdd then
        for _, v in ipairs(self._tmpAdd) do
            self._timers[#self._timers + 1] = v
        end
        self._tmpAdd = nil
    end
    self.timeMillisecond = self.timeSpend*1000
    --print("==== scheduler.onUpdate", self.millisecond)
end

function P:_addTimer(d)
    if self._running then
        if not self._tmpAdd then
            self._tmpAdd = {d}
        else
            self._tmpAdd[#self._tmpAdd+1] = d
        end
    else
        self._timers[#self._timers + 1] = d
    end
end

function bee.update(dt)
    P:onUpdate(dt)
    bee._emitWaitEvt()
    bee._updateTask(dt)

    for _, v in pairs(P._updater) do
        v(dt)
    end

    if bee._emiting then
        print("[event] bee.emit is stop by error", bee._emiting)
        bee._emiting = nil
    end
end

function bee.fixedUpdate(dt)
    for _, v in pairs(P._fixer) do
        v(dt)
    end
end

-- 执行一次延时方法
bee.once = function(dt, cb, target)
    return P:once(dt, cb, target)
end

-- 间隔 dt 重复执行 num 次
bee.repeatN = function(num, dt, cb, target)
    return P:repeatN(num, dt, cb, target)
end

-- 执行循环定时器
bee.schedule = function(dt, cb, target)
    return P:schedule(dt, cb, target)
end

bee.addUpdater = function(cb)
    P._updater[#P._updater + 1] = cb
end

bee.removeUpdater = function(cb)
    for k, v in ipairs(P._updater) do
        if v == cb then
            table.remove(P._updater, k)
            break
        end
    end
end

bee.addFixedUpdater = function(cb)
    P._fixer[#P._fixer + 1] = cb
end

bee.removeFixedUpdater = function(cb)
    for k, v in ipairs(P._fixer) do
        if v == cb then
            table.remove(P._fixer, k)
            break
        end
    end
end

