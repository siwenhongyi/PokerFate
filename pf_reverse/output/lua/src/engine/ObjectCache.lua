-- 游戏对象缓存池
local P = {
    _caches = {},   -- 缓存对象列表 {tag = {obj, obj, ...}, ...}
    _incaches = {}, -- 已经在缓存中的物体
    _tags = {},     -- {obj = tag}
    _delays = {},   -- 延迟回收的列表 {{obj = obj, dt = dt, tag = tag}}
    _prefabs = {},  -- 已经加载的预制体

    _root = nil,    -- 挂载物体的根节点
}
ObjectCache = P

function P:initRoot()
    if not self._root and CU.GameObject then
        local root = CU.GameObject("ObjectCache")
        CU.GameObject.DontDestroyOnLoad(root)
        self._root = root.transform

        scheduler:schedule(0, function(dt)
            self:onUpdate(dt)
        end)
    end
end

function P:getRoot()
    return self._root
end

-- 获取缓存的数量，isAll: 是否统计在 update 中等待回收的数量
function P:getCount(tag, isAll)
    local ret, tbr = 0, self._caches[tag]
    if tbr then
        ret = #tbr
    end
    if isAll and self._delays then
        for _, v in ipairs(self._delays) do
            if v.tag == tag then
                ret = ret + 1
            end
        end
    end
    return ret
end

function P:getTag(obj)
    return self._tags[obj]
end

-- 获取一个标记为 tag 的对象，如果不存在，则使用 prefab 创建
function P:getItem(tag, prefab)
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
        local obj = CU.GameObject.Instantiate(prefab)
        obj:SetActive(true)
        self._tags[obj] = tag
        return obj
    end
end

-- 获取一个名为 name 的预制体的实例
function P:getItemWithName(name)
    local obj = self:getItem(name)
    if not obj then
        obj = bee.createObj(name)
        if obj then
            obj:SetActive(true)
            self._tags[obj] = name
            return obj
        end
    end
    return obj
end

function P:addItemWithNameAsyn(name)
    ResManager:InstantiateObjectAsyn(name .. ".prefab", function(obj)
        if obj then
            obj:SetActive(true)
            self._tags[obj] = name
            self:putItem(obj)
        end
    end)
end

-- 归还对象，dt: 有值则会在 dt 时间后归还
function P:putItem(obj, dt)
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

function P:_putItem(obj, tag)
    if not bee.isNull(obj) and tag then
        if self._incaches[obj] then
            return
        end
        local tbr = self._caches[tag]
        if not tbr then
            self._caches[tag] = {obj}
        else
            tbr[#tbr+1] = obj
        end
        if self._root then
            obj.transform:SetParent(self._root, false)
        end
        obj:SetActive(false)
    end
end

function P:clearAll()
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
    if self._root then
        CU.GameObject.Destroy(self._root.gameObject)
        self._root = null
    end
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

