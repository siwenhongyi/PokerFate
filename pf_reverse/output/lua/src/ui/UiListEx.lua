local P = class("UiListEx")
UiListEx = P

-- 扩展 ScrollRect，使它能动态创建节点

function P:ctor(list)
    self.node = list
    self._list = list:GetComponent("ScrollRect")
    self._content = self._list.content
    self._horizontal = self._list.horizontal
    self._createFunc = nil
    self._refreshFunc = nil
    self._flexFunc = nil    -- 弹性位置计算函数
    self._isDirty = false
    self._width = 0
    self._wTable = nil
    self._shows = {}
    self._items = {}    -- 节点列表 {data = data, node = node, w = width, pos = pos, index = index}
    self._caches = {}   -- 节点缓存列表
    self._size = bee.v2(0, 0)
    self._spacing = 0
    self._top = 0
    self._bottom = 0
    self._rowCount = 1  -- 每行有几个元素
	self._customValueChange=false
    self._isInitShow = false
    self._itemStartTime = 0     -- 开始位移时间
    self._itemSpacingTime = 0.05 --元素间隔时间
    self._itemMoveTime = 0.2 --元素位移时间
    self._shakeOffset = 40 --横向回弹距离
    self._shakeTime = 0.1 --回弹时间
    self._list.onValueChanged:AddListener(function(v)
        self._isDirty = true
        self:refreshUi()
        
        if self._toTopFunc or self._toBottomFunc then
            if self._horizontal then
                if self._toTopFunc and v.x <= -0.01 then
                    self._toTopFunc()
                elseif self._toBottomFunc and v.x >= 1.01 then
                    self._toBottomFunc()
                end
            else
                if self._toTopFunc and v.y >= 1.01 then
                    self._toTopFunc()
                elseif self._toBottomFunc and v.y <= -0.01 then
                    self._toBottomFunc()
                end
            end
        end
        
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

-- 滚动到顶部和底部的回调函数
function P:setScrollToTopFunc(fn)
    self._toTopFunc = fn
end

function P:setScrollToBottomFunc(fn)
    self._toBottomFunc = fn
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

function P:setRowCount(count)
    self._rowCount = count
end

-- 设置每列元素的 x 位置
function P:setRowPostions(poses)
    self._rowPoses = poses
end

function P:setListShow()
    self._isInitShow = true
end

function P:hideListShow()
    self._isInitShow = false
end

function P:setShowTime(start, space, move)
    if start then self._itemStartTime = start end
    if space then self._itemSpacingTime = space end
    if move then self._itemMoveTime = move end
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
        self._items = {}
    end
end

-- 设置基础数据 不规则大小的列表每个数据需要有 __kind 字段来标识它的大小和类型
-- 类会使用 __width 和 __pos 来存储元素的大小和实际位置
function P:setDatas(datas, isInit, refresh)
    if isInit == nil then isInit = true end
    if #self._items > 0 then
        for _, v in ipairs(self._items) do
            if not bee.isNull(v.node) then
                self._caches[#self._caches + 1] = {v.node, v.data.__kind}
                v.node:SetActive(false)
                v.node = nil
            end
        end
        self._items = {}
    end
    self._shows = {}
    for k, v in ipairs(datas) do
        self._items[#self._items + 1] = {data = v, node = nil, w = 0, pos = 0, index = k}
    end
    self._isDirty = true
    self:refreshItemsW()
    if refresh ~= false then
        self:refreshUi(isInit)
    end
end

-- 追加数据
function P:append(datas)
    local i = #self._items + 1
    for _, v in ipairs(datas) do
        self._items[i] = {data = v, node = nil, w = 0, pos = 0, index = i}
        i = i + 1
    end
    self._isDirty = true

    self:refreshItemsW()

    for _, v in ipairs(self._shows) do
        local d = self._items[v]
        if d and not bee.isNull(d.node) then
            self:_resetItemPos(d, d.node)
            -- d.node.transform.localPosition = bee.v3(self._size.x / 2, -d.pos - d.w / 2, 0)
        end
    end
    self:refreshUi()
end

-- 插入数据, index: 插入位置 data: 数据 slideDt: 插入动画，可为空 node: 插入的节点，可为空
function P:insertItem(index, data, slideDt, node)
    local d = {data = data, node = node, w = 0, pos = 0, index = index}
    table.insert(self._items, index, d)
    for k, vv in ipairs(self._items) do
        vv.index = k
    end
    self:refreshItemsW()
    self._shows = {}
    self._slideIndex = index + 1
    self._slideDt = slideDt
    self._slideDir = 1
    self._isDirty = true
    self:refreshUi()
    self._slideIndex = nil
    self._slideDt = nil
    self._slideDir = nil
end

function P:removeData(data, slideDt, noCache)
    for k, v in ipairs(self._items) do
        if v.data == data then
            if not bee.isNull(v.node) then
                self:removeItem(v.node, slideDt, noCache)
            else
                table.remove(self._items, k)
                self:refreshUI()
            end
            break
        end
    end
end

-- 删除元素，slideDt: 不为空则表示需要使用动画进行合并
-- noCache: node 不缓存到列表队列中
-- 返回对应的数据 data
function P:removeItem(node, slideDt, noCache)
    for _, v in ipairs(self._shows) do
        local d = self._items[v]
        if d and d.node == node then
            if not noCache then
                self._caches[#self._caches + 1] = {d.node, d.data.__kind}
                d.node:SetActive(false)
            end
            d.node = nil
            table.remove(self._items, v)
            for k, vv in ipairs(self._items) do
                vv.index = k
            end
            self:refreshItemsW()
            self._shows = {}
            self._slideIndex = v
            self._slideDt = slideDt
            self._slideDir = -1
            self._isDirty = true
            self:refreshUi()
            self._slideIndex = nil
            self._slideDt = nil
            self._slideDir = nil
            return d.data
        end
    end
    return nil
end

function P:refreshUi(isInit)
    if not self._isDirty or bee.isNull(self._list) or not self._listSize then
        return
    end
    if isInit and self._isInitShow == true then
        self._list.enabled = false
    end
    self._isDirty = false
    local shows = self:_getCurShows()
    local news = self:_getExpect(shows, self._shows)
    local olds = self:_getExpect(self._shows, shows)
    self._shows = shows
    
    if olds then
        for _, v in ipairs(olds) do
            local d = self._items[v]
            if d and not bee.isNull(d.node) then
                self._caches[#self._caches + 1] = {d.node, d.data.__kind}
                d.node:SetActive(false)
                d.node = nil
            end
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
                    if isInit and self._isInitShow == true then
                        self:_resetItemPos(d, d.node)
                    else
                        self:_resetItemPos(d, d.node)
                    end
                    
                    if self._refreshFunc then
                        self._refreshFunc(d.data, d.node, isInit, index)
                    end
                end
            end
        end
    end

    if self._slideDt then
        for v, _ in ipairs(self._items) do
            if v >= self._slideIndex then
                local d = self._items[v]
                if d and d.node then
                    if d.index >= self._slideIndex then
                        local p1 = d.node.transform.localPosition
                        local p2 = bee.v3(p1.x, p1.y + d.w * self._slideDir + self._spacing * self._slideDir)
                        d.node.transform.localPosition = p2
                        bee.tween(d.node)
                        : to(self._slideDt, {position = p1})
                        : link(d.node)
                    end
                end
            end
        end
    end
    if (olds or news) and self._customValueChange then
        self._customValueChange()
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

function P:refreshDataItem(data)
    for _, v in ipairs(self._shows) do
        local d = self._items[v]
        if d and d.data == data and d.node and self._refreshFunc then
            self._refreshFunc(d.data, d.node)
            break
        end
    end
end

function P:_resetItemPos(d, node)
    local pos = nil
    if self._horizontal then
        pos = bee.v3(d.pos + d.w / 2, 0, 0)
    else
        if self._rowCount > 1 then
            local i = d.index % self._rowCount
            if i == 0 then i = self._rowCount end
            if self._rowPoses and self._rowPoses[i] then
                pos = bee.v3(self._rowPoses[i] + self._size.x / 2, -d.pos - d.w / 2, 0)
            else
                local x = self._size.x / (self._rowCount)
                pos = bee.v3(x * (i - 0.5) - self._size.x / 2, -d.pos - d.w / 2, 0)
            end
        else
            pos = bee.v3(self._size.x / 2, -d.pos - d.w / 2, 0)
        end
    end
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

    local pos, isNext = self._top, true
    for k, v in ipairs(self._items) do
        if self._wTable then
            v.w = self._wTable[v.data.__kind]
        else
            v.w = self._width
        end
        if self._rowCount > 1 then
            isNext = (v.index % self._rowCount) == 0
        end
        v.pos = pos
        if isNext or k == #self._items then
            pos = pos + v.w
            if k < #self._items then
                pos = pos + self._spacing
            end
        end
    end
    local s = self._content.transform.sizeDelta
    if self._horizontal then
        self._size.x, self._size.y = pos + self._bottom, s.y 
    else
        self._size.x, self._size.y = s.x, pos + self._bottom
    end
    self._content.transform.sizeDelta = self._size
end

function P:isDataShowing(data)
    for _, v in ipairs(self._shows) do
        if data == self._items[v].data then
            return not bee.isNull(self._items[v].node)
        end
    end
    return false
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
    local y1, y2
    if self._horizontal then
        y1, y2 = -pos.x, -pos.x + self._listSize.x
    else
        y1, y2 = pos.y, pos.y + self._listSize.y
    end
    -- 直接遍历，可考虑使用二分法
    for k, v in ipairs(self._items) do
        if v.pos > y2 then
            break
        end
        if v.pos + v.w >= y1 then
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
function P:moveToYItem(index, isTween, offsetY, callback, refresh)
    local d = self._items[index]
    if d then
        local y, toPos = d.pos, nil
        if self._horizontal then
            if self._size.x <= self._listSize.x then
                return
            end
            if y > self._size.x - self._listSize.x then
                y = self._size.x - self._listSize.x
            end
            if offsetY then
                y = y + offsetY
            end
            toPos = bee.v3(-y, self._content.transform.localPosition.y, 0)
        else
            if self._size.y <= self._listSize.y then
                return
            end
            if y > self._size.y - self._listSize.y then
                y = self._size.y - self._listSize.y
            end
            if offsetY then
                y = y + offsetY
            end
            toPos = bee.v3(self._content.transform.localPosition.x, y, 0)
        end
        if isTween then
            local dt = 0.2
            if type(isTween) == "number" then
                dt = isTween
            end
            bee.tween(self._content)
            : to(dt, {position = toPos})
            :onComplete(function ()
				if callback then
					callback()
				end
			end)
        else
            self._content.transform.localPosition = toPos
            if callback then
                callback()
            end
        end
        self._isDirty = true
        if refresh ~= false then
            self:refreshUi()
        end
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
    self:refreshUi()
end

function P:moveToEnd(isTween)
    self:moveToYItem(#self._items, isTween)
end

function P:moveItemTo(from, to, scrollDt, moveDt, scaleDt, cb, startCb)
    local item = self._items[from]
    local toItem = self._items[to]
    if item and toItem then
        local node = item.node
        node.transform:SetParent(self.node.transform)
        item.node = nil
        item.data.__notNode = true
        if scaleDt then
            node.transform.localScale = bee.v3(1.1, 1.1, 1.1)
        end
        local _onScrollEnd = function()
            if startCb then startCb() end
            item.data.__notNode = nil
            node.transform:SetParent(self._content.transform)
            bee.tween(node, true)
            : to(moveDt or 0.5, {position = toItem.node.transform.position})
            : onComplete(function()
                table.remove(self._items, from)
                self:insertItem(to, item.data, 0.5, node)
                if scaleDt then
                    bee.tween(node)
                    : to(scaleDt, {scale = bee.v3(1, 1, 1)})
                end
                if cb then
                    cb()
                end
                if self._refreshFunc then
                    for _, d in ipairs(self._items) do
                        if d.node then
                            self._refreshFunc(d.data, d.node)
                        end
                    end
                end
            end)
            : link()
        end
        
        local toItem2 = self._items[to - 2] or self._items[to - 1] or toItem
        if self._content.transform.localPosition.y > toItem2.pos then
            local spd = self._size.y / scrollDt
            local h = self._content.transform.localPosition.y  - toItem2.pos
            self:moveToYItem(toItem2.index, h / spd, 0, function()
                _onScrollEnd()
            end)
        else
            _onScrollEnd()
        end
        return node
    end
    return nil
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
