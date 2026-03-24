-- 对象缓存池
local P = class("NodeCache")
NodeCache = P

function P:ctor(cacheCount, inGobal)
    self._caches = {}   -- 缓存对象列表 {tag = {obj, obj, ...}, ...}
    self._incaches = {} -- 已经在缓存中的物体
    self._tags = {}     -- {obj = tag}
    self._delays = {}   -- 延迟回收的列表 {{obj = obj, dt = dt, tag = tag}}
    self._prefabs = {}  -- 已经加载的预制体

    self._inUsings = {} -- 正在被使用的节点列表，用于缓存回收节点
    self._maxCacheCount = cacheCount or 10
    self._inGobal = inGobal
end
-- 获取一个标记为 tag 的对象，如果不存在，则使用 prefab 创建
function P:getItem(tag, prefab, parent)
    local tbr = self._caches[tag]
    if tbr and #tbr > 0 then
        while #tbr > 0 do
            local obj = table.remove(tbr, #tbr)
            self._incaches[obj] = nil
            if not bee.isNull(obj) then
                obj:SetActive(true)
                return obj
            end
        end
    end
    if prefab then
        local obj
        if parent then
            obj = CU.GameObject.Instantiate(prefab, parent, false)
        else
            obj = CU.GameObject.Instantiate(prefab)
        end
        obj:SetActive(true)
        self._tags[obj] = tag
        return obj
    end
end

-- 获取一个名为 name 的预制体的实例
function P:getItemWithName(name, parent)
    local obj = self._inGobal and ObjectCache:getItem(name)
    if obj then
        if parent then
            obj.transform:SetParent(parent, false)
        end
        return obj
    end
    obj = self:getItem(name)
    if not obj then
        local prefab = self._prefabs[name]
        if not prefab then
            prefab = ResManager:GetPrefab(name .. ".prefab")
        end
        if prefab then
            self._prefabs[name] = prefab
            if parent then
                obj = CU.GameObject.Instantiate(prefab, parent, false)
            else
                obj = CU.GameObject.Instantiate(prefab)
            end
            obj:SetActive(true)
            self._tags[obj] = name
            return obj
        end
    elseif parent then
        obj.transform:SetParent(parent, false)
    end
    return obj
end

function P:preloadItem(name, parent)
    local prefab = self._prefabs[name]
    if not prefab then
        prefab = ResManager:GetPrefab(name .. ".prefab")
    end
    if prefab then
        self._prefabs[name] = prefab
        self:preloadPrefabItem(name, prefab, parent)
    end
end

function P:preloadPrefabItem(name, prefab, parent)
    if prefab then
        local obj = nil
        if parent then
            obj = CU.GameObject.Instantiate(prefab, parent.transform)
        else
            obj = CU.GameObject.Instantiate(prefab)
        end
        obj:SetActive(false)
        self._tags[obj] = name
        self:_putItem(obj, name)
    end
end

-- 归还对象，dt: 有值则会在 dt 时间后归还
function P:putItem(obj, dt)
    self:removeUsing(obj)
    if self._inGobal and ObjectCache:getTag(obj) then
        ObjectCache:putItem(obj, dt)
        return
    end
    local tag = self._tags[obj]
    if tag then
        if not dt then
            self:_putItem(obj, tag)
        else
            self._delays[#self._delays+1] = {obj = obj, dt = dt, tag = tag}
        end
    else
        if dt then
            CU.GameObject.Destroy(obj, dt)
        else
            CU.GameObject.Destroy(obj)
        end
    end
end

-- 立即归还对象
function P:putItemImm(obj)
    self:_putItem(obj, self._tags[obj])
    for k, v in ipairs(self._delays) do
        if v.obj == obj then
            table.remove(self._delays, k)
            break
        end
    end
end

function P:getDelayCount()
    return #self._delays
end

function P:_putItem(obj, tag)
    if not bee.isNull(obj) and tag then
        if self._incaches[obj] then
            return
        end
        local tbr = self._caches[tag]
        if not tbr then
            self._caches[tag] = {obj}
            self._incaches[obj] = true
        else
            if #tbr >= self._maxCacheCount then
                self._tags[obj] = nil
                CU.GameObject.Destroy(obj)
                return
            end
            tbr[#tbr+1] = obj
            self._incaches[obj] = true
        end
        obj:SetActive(false)
        return true
    end
    return false
end

function P:addUsing(node)
    self._inUsings[node] = true
end

function P:removeUsing(node)
    self._inUsings[node] = nil
end

function P:resetInUsings(killTween)
    for k, _ in pairs(self._inUsings) do
        if killTween then
            bee.Tween.killByTarget(k)
        end
        self:putItem(k)
        self._inUsings[k] = nil
    end
end

function P:clearAll()
    self:resetInUsings(true)
    for _, objs in pairs(self._caches) do
        for _, v in ipairs(objs) do
            CU.GameObject.Destroy(v)
        end
    end
    for _, v in ipairs(self._delays) do
        CU.GameObject.Destroy(v.obj)
    end
    self._caches = {}
    self._incaches = {}
    self._tags = {}
    self._delays = {}
    self._prefabs = {}
end

function P:onUpdate(dt)
    for i = #self._delays, 1, -1 do
        local v = self._delays[i]
        v.dt = v.dt - dt
        if v.dt <= 0 then
            self:_putItem(v.obj, v.tag)
            table.remove(self._delays, i)
        end
    end
end

