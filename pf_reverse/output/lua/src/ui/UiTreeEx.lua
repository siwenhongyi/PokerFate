local P = class("UiTreeEx")
UiTreeEx = P

-- 扩展 ScrollRect，实现树形控件

function P:ctor(list)
    self.node = list
    self._list = list:GetComponent("ScrollRect")
    self._content = self._list.content
    self._createFunc = nil
    self._refreshFunc = nil
    self._flexFunc = nil    -- 弹性位置计算函数
    self._isDirty = false
    self._width = 0
    self._wTable = nil
    self._shows = {}
    self._itemTree = {}    -- 树形节点列表 {data = data, node = node, w = width, pos = pos, index = index, children = {}, showing = true}
    self._items = {} -- 所有节点的顺序列表
    self._caches = {}   -- 节点缓存列表
    self._size = bee.v2(0, 0)
    self._spacing = 0
    self._top = 0
    self._bottom = 0

    self._list.onValueChanged:AddListener(function(v)
        self._isDirty = true
        self:refreshUI()

        if self._flexFunc then
            for _, v in ipairs(self._shows) do
                local d = self._items[v]
                if d and d.node then
                    self:_resetItemPos(d, d.node)
                end
            end
        end
    end)
end

-- 设置创建节点的回调方法 fn(data)，返回元素节点
function P:setCreateFunc(fn)
    self._createFunc = fn
end

-- 设置刷新节点的回调方法 fn(data, node)
function P:setRefreshFunc(fn)
    self._refreshFunc = fn
end

-- 设置弹性位置变化 fn(data, item, pos) return pos
function P:setFlexFunc(fn)
    self._flexFunc = fn
end

-- 设置 width 如果是整个数字，则表示这是个固定大小的列表
-- 如果 width 是个 table，则是不规则大小，使用 width[data.__kind] 来获取这个元素的大小
function P:setWidth(width)
    if type(width) == "table" then
        self._wTable = width
    else
        self._width = width
        self._wTable = nil
    end
end

-- 设置元素间距
function P:setSpacing(val)
    self._spacing = val
end

-- 设置上下间距
function P:setTopBottom(top, bottom)
    self._top, self._bottom = top, bottom
end

function P:setListSize(width,height)
	self._listSize = bee.v2(width, height)
end

-- 添加所有节点及数据
function P:clear()
    if #self._items > 0 then
        for _, v in ipairs(self._items) do
            if not bee.isNull(v.node) then
                CU.GameObject.Destroy(v.node)
                v.node = nil
            end
        end
        self._itemTree = {}
        self._items = {}
    end
end

-- 设置基础数据 不规则大小的列表每个数据需要有 __kind 字段来标识它的大小和类型，使用 children 来包含下级数据列表，explsed 是否展开数据
-- 类会使用 __width 和 __pos 来存储元素的大小和实际位置
--[[
    -- 树形结构定义范例
    datas = {
        {id=数据id, value = 数据值, children=下级数据列表, explsed=是否展开数据},
    }
]]
function P:setDatas(datas, isInit)
    if isInit == nil then isInit = true end
    if #self._items > 0 then
        for _, v in ipairs(self._items) do
            self:_putCache(v)
        end
        self._itemTree = {}
        self._items = {}
    end
    self._shows = {}
    self:_initDatas(self._itemTree, datas, 0, true)
    
    self._isDirty = true
    self:refreshItemsW()
    self:refreshUI(isInit)
end

function P:_initDatas(items, datas, index, showing)
    for k, v in ipairs(datas) do
        local item = {data = v, node = nil, w = 0, pos = 0, index = k + index, showing = showing}
        items[#items + 1] = item
        self._items[#self._items + 1] = item
        if v.children then
            item.children = {}
            self:_initDatas(item.children, v.children, (k + index) * 1000, v.explsed)
        end
    end
end

function P:refreshUI(isInit)
    if not self._isDirty or bee.isNull(self._list) or not self._listSize then
        return
    end
    
    self._isDirty = false
    local shows = self:_getCurShows()
    local news = self:_getExpect(shows, self._shows)
    local olds = self:_getExpect(self._shows, shows)
    self._shows = shows
    
    if olds then
        for _, v in ipairs(olds) do
            self:_putCache(self._items[v])
        end
    end
    if news then
        for index, v in ipairs(news) do
            local d = self._items[v]
            if d and not d.data.__notNode then
                if bee.isNull(d.node) then
                    d.node = self:_getCache(d.data.__kind)
                    if d.node then
                        d.node:SetActive(true)
                        bee.Tween.killByTarget(d.node)
                    end
                end
                if bee.isNull(d.node) and self._createFunc then
                    d.node = self._createFunc(d.data)
                    if d.node then
                        d.node:SetActive(true)
                        d.node.transform:SetParent(self._content.transform, false)
                    end
                end
                if d.node then
                    self:_resetItemPos(d, d.node)
                    
                    if self._refreshFunc then
                        self._refreshFunc(d.data, d.node)
                    end
                end
            end
        end
    end

    if olds or news then
        for k, v in ipairs(self._shows) do
            self:_resetItemPos(self._items[v], self._items[v].node)
        end
        if self._customValueChange then
            self._customValueChange()
        end
    end
end

function P:refreshShowingUi()
    for _, v in ipairs(self._shows) do
        local d = self._items[v]
        if d and d.node and self._refreshFunc then
            self._refreshFunc(d.data, d.node)
        end
    end
end

function P:_resetItemPos(d, node)
    local pos = bee.v3(self._size.x / 2, -d.pos - d.w / 2, 0)
    if self._flexFunc then
        d.node.transform.localPosition = self._flexFunc(d.data, d.node, pos)
    else
        d.node.transform.localPosition = pos
    end
end

function P:refreshSize()
    if not self._listSize or self._listSize.y <= 0 then
        local r = self._list.transform.rect
        self:setListSize(r.width, r.height)
    end
end

function P:refreshItemsW()
    self:refreshSize()
    self._pos = self._top
    self:_refreshItemsW(self._itemTree)
    
    local s = self._content.transform.sizeDelta
    self._size.x, self._size.y = s.x, math.max(self._pos + self._bottom, self._listSize.y)
    self._content.transform.sizeDelta = self._size
end

function P:_refreshItemsW(items)
    for k, v in ipairs(items) do
        if self._wTable then
            v.w = self._wTable[v.data.__kind]
        else
            v.w = self._width
        end
        if self._pos > self._top then
            self._pos = self._pos + self._spacing
        end
        v.pos = self._pos
        self._pos = self._pos + v.w
        v.showing = true

        if v.children then
            if v.data.explsed then
                self:_refreshItemsW(v.children)
            else
                self:_setItemShowing(v.children, false)
            end
        end
    end
end

function P:_setItemShowing(items, showing)
    for _, v in ipairs(items) do
        v.showing = showing
        if v.children then
            self:_setItemShowing(v.children, showing)
        end
    end
end

function P:isDataShowing(data)
    for _, v in ipairs(self._shows) do
        if data == self._items[v].data then
            return not bee.isNull(self._items[v].node)
        end
    end
    return false
end

function P:setExplsed(data)
    if data.explsed then
        data.explsed = nil
    else
        data.explsed = true
    end
    self:refreshItemsW()
    self:refreshUI()
end

function P:getData(index)
    if self._items[index] then return self._items[index].data end
    return nil
end

function P:getDataNode(data)
    for _, v in ipairs(self._items) do
        if v.data == data then
            return v.node
        end
    end
    return nil
end

function P:getNode(index)
    if self._items[index] then return self._items[index].node end
    return nil
end

function P:getIndex(data)
    for k, v in ipairs(self._items) do
        if v.data == data then
            return k
        end
    end
    return 0
end

function P:getShows()
    return self._shows
end

function P:_getCurShows()
    local pos = self._content.transform.localPosition
    local shows = {}
    local y1, y2 = pos.y, pos.y + self._listSize.y
    -- 直接遍历，可考虑使用二分法
    for k, v in ipairs(self._items) do
        if v.showing and v.pos > y2 then
            break
        end
        if v.showing and v.pos + v.w >= y1 then
            shows[#shows + 1] = k
        end
        -- if v.pos + v.w > y2 then
        --     break
        -- end
    end
    return shows
end

function P:_getExpect(shows1, shows2)
    local flag = false
    local news = nil
    for _, v in ipairs(shows1) do
        flag = true
        for _, vv in ipairs(shows2) do
            if vv == v then
                flag = false
                break
            end
        end
        if flag then
            if not news then
                news = {v}
            else
                news[#news + 1] = v
            end
        end
    end
    return news
end

function P:_putCache(v)
    if v and not bee.isNull(v.node) then
        self._caches[#self._caches + 1] = {v.node, v.data.__kind}
        v.node:SetActive(false)
        v.node = nil
    end
end

function P:_getCache(kind)
    for k, v in ipairs(self._caches) do
        if v[2] == kind then
            table.remove(self._caches, k)
            return v[1]
        end
    end
    return nil
end

function P:verticalPosition()
	return self._list.verticalNormalizedPosition
end

--移动到指定index处
function P:moveToYItem(index, isTween, offsetY, callback)
    local d = self._items[index]
    if d then
        if self._size.y <= self._listSize.y then
            return
        end
        local y = d.pos
        if y > self._size.y - self._listSize.y then
            y = self._size.y - self._listSize.y
        end
        if offsetY then
            y = y + offsetY
        end
        if isTween then
            local dt = 0.2
            if type(isTween) == "number" then
                dt = isTween
            end
            bee.tween(self._content)
            : to(dt, {position = bee.v3(self._content.transform.localPosition.x, y, 0)})
            :onComplete(function ()
				if callback then
					callback()
				end
			end)
        else
            self._content.transform.localPosition = bee.v3(self._content.transform.localPosition.x, y, 0)
            if callback then
                callback()
            end
        end
        self._isDirty = true
        self:refreshUI()
    end
end

-- 移动指定高度
function P:moveAddY(addY, isTween)
    if isTween then
        local dt = 0.2
        if type(isTween) == "number" then
            dt = isTween
        end
        bee.tween(self._content)
        : to(dt, {position = bee.v3(self._content.transform.localPosition.x, self._content.transform.localPosition.y + addY, 0)})
    else
        self._content.transform.localPosition = bee.v3(self._content.transform.localPosition.x, self._content.transform.localPosition.y + addY, 0)
    end
    self._isDirty = true
    self:refreshUI()
end

function P:moveToEnd(isTween)
    self:moveToYItem(#self._items, isTween)
end

function P:addValueChanged(changeCb)
	self._customValueChange=changeCb
end

function P:getDatas()
    return self._items
end

function P:getDatasCount()
    return #self._items
end

return P
