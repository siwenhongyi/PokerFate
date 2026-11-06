local P = class("RecordDataModel", BaseModel)
RecordDataModel = P

-- 页大小
local PAGE_SIZE = 20

function P:ctor()
    -- 最近记录
    self.recentList = {}
    self.recentSkip = 0
    self.recentTotal = 0
    self._recentLoading = false
    self._recentDirty = true
    self._recentGameTypeArr = nil

    -- 收藏记录
    self.collectList = {}
    self.collectSkip = 0
    self.collectTotal = 0
    self._collectLoading = false
    self._collectInited = false
    self._collectDirty = true
    self._collectGameTypeArr = nil

    self._allCollects = {}  -- 所有获取回来的收藏

    P.super.ctor(self)
end

function P:afterLogin()
    self:resetRecent()
    self:resetCollect()
end

-- ============================== 最近记录 ==============================

-- 比较两个 game_type 数组是否相同
---@param a table|nil
---@param b table|nil
---@return boolean
function P:_isSameGameTypeArr(a, b)
    if a == b then return true end
    if not a or not b then return false end
    if #a ~= #b then return false end
    for i = 1, #a do
        if a[i] ~= b[i] then return false end
    end
    return true
end

--- 获取最近记录 (首次加载)
---@param gameTypeArr table|nil 牌局类型数组 (nil = 全部)
---@param cb function 回调 function(success, list, total)
function P:fetchRecentList(gameTypeArr, cb)
    -- game_type 变了，标记脏数据
    if not self:_isSameGameTypeArr(self._recentGameTypeArr, gameTypeArr) then
        self._recentDirty = true
    end
    -- 数据未变脏，直接返回缓存
    if not self._recentDirty and #self.recentList > 0 then
        bee.once(-1, function()
            if cb then cb(true, self.recentList, self.recentTotal) end
        end)
        return
    end

    self._recentLoading = true
    self.recentSkip = 0
    self._recentGameTypeArr = gameTypeArr

    Net:post("collCard/recentlyCardList", {
        skip = 0,
        lang = LAN:getLanguage(),
        game_type_arr = gameTypeArr,
    }, function(data)
        self._recentLoading = false
        if 0 == data.code then
            self.recentList = data.list or {}
            self.recentSkip = table.nums(self.recentList)
            self.recentTotal = data.total or 0
            self._recentDirty = false

            bee.emit("evt_RecentListUpdated", self.recentList, self.recentTotal)
            if cb then cb(true, self.recentList, self.recentTotal) end
        else
            if cb then cb(false) end
        end
    end)
end

--- 加载更多最近记录 (追加)
---@param cb function 回调 function(success, newList, hasMore)
function P:fetchMoreRecent(cb)
    if self._recentLoading then
        return
    end
    if not self:hasMoreRecent() then
        if cb then cb(true, {}, false) end
        return
    end

    self._recentLoading = true
    Net:post("collCard/recentlyCardList", {
        skip = self.recentSkip,
        lang = LAN:getLanguage(),
        game_type_arr = self._recentGameTypeArr,
    }, function(data)
        self._recentLoading = false
        if 0 == data.code then
            local newList = data.list or {}
            for _, v in ipairs(newList) do
                table.insert(self.recentList, v)
            end
            self.recentSkip = self.recentSkip + table.nums(newList)
            self.recentTotal = data.total or self.recentTotal

            local hasMore = self.recentSkip < self.recentTotal
            bee.emit("evt_RecentListMore", newList, hasMore)
            if cb then cb(true, newList, hasMore) end
        else
            if cb then cb(false) end
        end
    end)
end

function P:hasMoreRecent()
    return self.recentSkip < self.recentTotal
end

--- 标记最近记录为脏，下次 fetchRecentList 时强制重新拉取
function P:markRecentDirty()
    self._recentDirty = true
end

function P:resetRecent()
    self.recentList = {}
    self.recentSkip = 0
    self.recentTotal = 0
    self._recentLoading = false
    self._recentDirty = true
    self._recentGameTypeArr = nil
end

-- ============================== 收藏记录 ==============================

--- 获取收藏记录 (首次加载)
---@param gameTypeArr table|nil 牌局类型数组 (nil = 全部)
---@param cb function 回调 function(success, list, total)
function P:fetchCollectList(gameTypeArr, cb)
    -- game_type 变了，标记脏数据
    if not self:_isSameGameTypeArr(self._collectGameTypeArr, gameTypeArr) then
        self._collectDirty = true
    end
    -- 数据未变脏，直接返回缓存
    if not self._collectDirty and #self.collectList > 0 then
        bee.once(-1, function()
            if cb then cb(true, self.collectList, self.collectTotal) end
        end)
        return
    end

    self._collectLoading = true
    self.collectSkip = 0
    self._collectInited = true
    self._collectGameTypeArr = gameTypeArr

    Net:post("collCard/v2List", {
        skip = 0,
        lang = LAN:getLanguage(),
        game_type_arr = gameTypeArr,
    }, function(data)
        self._collectLoading = false
        if 0 == data.code then
            self.collectList = data.list or {}
            for _, v in ipairs(self.collectList) do
                self._allCollects[v.gameid] = v
            end
            self.collectSkip = table.nums(self.collectList)
            self.collectTotal = data.total or 0
            self._collectDirty = false
            PlayerModel:setCurRecord(self.collectTotal)

            bee.emit("evt_CollectListUpdated", self.collectList, self.collectTotal)
            if cb then cb(true, self.collectList, self.collectTotal) end
        else
            if cb then cb(false) end
        end
    end)
end

--- 加载更多收藏记录 (追加)
---@param cb function 回调 function(success, newList, hasMore)
function P:fetchMoreCollect(cb)
    if self._collectLoading then
        return
    end
    if not self:hasMoreCollect() then
        if cb then cb(true, {}, false) end
        return
    end

    self._collectLoading = true
    Net:post("collCard/v2List", {
        skip = self.collectSkip,
        lang = LAN:getLanguage(),
        game_type_arr = self._collectGameTypeArr,
    }, function(data)
        self._collectLoading = false
        if 0 == data.code then
            local newList = data.list or {}
            for _, v in ipairs(newList) do
                table.insert(self.collectList, v)
                self._allCollects[v.gameid] = v
            end
            self.collectSkip = self.collectSkip + table.nums(newList)
            self.collectTotal = data.total or self.collectTotal
            PlayerModel:setCurRecord(self.collectTotal)

            local hasMore = self.collectSkip < self.collectTotal
            bee.emit("evt_CollectListMore", newList, hasMore)
            if cb then cb(true, newList, hasMore) end
        else
            if cb then cb(false) end
        end
    end)
end

function P:hasMoreCollect()
    return self.collectSkip < self.collectTotal
end

function P:isCollectInited()
    return self._collectInited
end

--- 标记收藏记录为脏，下次 fetchCollectList 时强制重新拉取
function P:markCollectDirty()
    self._collectDirty = true
end

function P:resetCollect()
    self.collectList = {}
    self.collectSkip = 0
    self.collectTotal = 0
    self._collectLoading = false
    self._collectInited = false
    self._collectDirty = true
    self._collectGameTypeArr = nil
end

-- ============================== 收藏操作 ==============================

-- 更新所有缓存列表中指定 gameid 的 collected 属性
---@param gameid string
---@param collected boolean
function P:_setCollectedFlag(gameid, collected)
    for _, list in ipairs({self.recentList, self.collectList}) do
        for _, v in ipairs(list) do
            if v.gameid == gameid then
                v.collected = collected
                break
            end
        end
    end
    if self._allCollects[gameid] then
        self._allCollects[gameid].collected = collected
    end
end

-- 从列表中移除指定 gameid 的记录
---@param list table
---@param gameid string
function P:_removeByGameid(list, gameid)
    for i, v in ipairs(list) do
        if v.gameid == gameid then
            table.remove(list, i)
            return true
        end
    end
    return false
end

-- 检查列表中是否已存在指定 gameid 的记录
---@param list table
---@param gameid string
---@return boolean
function P:_findInList(list, gameid)
    for _, v in ipairs(list) do
        if v.gameid == gameid then
            return true
        end
    end
    return false
end

--- 收藏一条记录
---@param gameid string 牌局ID
---@param cb function
function P:addCollect(gameid, cb, roomid, tid)
    Net:post("/collCard/update", {
        add_id = gameid,
        lang = LAN:getLanguage(),
        roomid = roomid,
        tid = tid,
    }, function(d)
        if 0 == d.code then
            self.collectTotal = #d.gameids
            PlayerModel:setCurRecord(self.collectTotal)
            self:_setCollectedFlag(gameid, true)
            -- 查找记录并插入到收藏列表头部 (避免重复)
            local record = self:findRecord(gameid)
            if record and not self:_findInList(self.collectList, gameid) then
                table.insert(self.collectList, 1, record)
                self.collectSkip = self.collectSkip + 1
                self._allCollects[record.gameid] = record
            end
            bee.emit("evt_CollectChanged")
            if cb then cb(true) end

            if bee.isInGame() then
                self:markCollectDirty()
            end
        else
            if cb then cb(false) end
        end
    end)
end

--- 取消收藏
---@param gameid string 牌局ID
---@param cb function
function P:removeCollect(gameid, cb)
    Net:post("/collCard/update", {
        del_id = gameid,
        lang = LAN:getLanguage(),
    }, function(d)
        if 0 == d.code then
            self.collectTotal = #d.gameids
            PlayerModel:setCurRecord(self.collectTotal)
            self:_setCollectedFlag(gameid, false)
            -- 从本地列表移除
            self:_removeByGameid(self.collectList, gameid)
            self.collectSkip = self.collectSkip - 1
            bee.emit("evt_CollectChanged")
            if cb then cb(true) end

            if bee.isInGame() then
                self:markCollectDirty()
            end
        else
            if cb then cb(false) end
        end
    end)
end

--- 替换收藏 (删除旧记录同时添加新记录)
---@param removeId string 要移除的旧 gameid
---@param addId string 要添加的新 gameid
---@param cb function
function P:replaceCollect(removeId, addId, cb, roomid, tid)
    Net:post("/collCard/update", {
        del_id = removeId,
        add_id = addId,
        lang = LAN:getLanguage(),
        roomid = roomid,
        tid = tid,
    }, function(d)
        if 0 == d.code then
            self.collectTotal = #d.gameids
            PlayerModel:setCurRecord(self.collectTotal)
            self:_setCollectedFlag(removeId, false)
            self:_setCollectedFlag(addId, true)
            -- 从本地列表移除旧记录，插入新记录到头部
            self:_removeByGameid(self.collectList, removeId)
            local record = self:findRecord(addId)
            if record and not self:_findInList(self.collectList, addId) then
                table.insert(self.collectList, 1, record)
                self._allCollects[record.gameid] = record
            end
            bee.emit("evt_CollectChanged")
            if cb then cb(true) end

            if bee.isInGame() then
                self:markCollectDirty()
            end
        else
            if cb then cb(false) end
        end
    end)
end

--- 更新备注
---@param gameid string
---@param remark string
---@param cb function
function P:updateRemark(gameid, remark, cb)
    Net:post("/collCard/update", {
        gameid = gameid,
        remark = remark,
    }, function(d)
        if 0 == d.code then
            -- 更新本地缓存中的备注
            for _, list in ipairs({self.recentList, self.collectList}) do
                for _, v in ipairs(list) do
                    if v.gameid == gameid then
                        v.remark = remark
                        break
                    end
                end
            end
            bee.emit("evt_ReplayRemarkChanged", gameid, remark)
            if cb then cb(true) end
        else
            if cb then cb(false) end
        end
    end)
end

-- ============================== 牌局详情 & 导航 ==============================

--- 获取牌局详情
---@param gameid string
---@param cb function 回调 function(success, detailData)
function P:fetchGameDetail(gameid, cb)
    Net:post("/collCard/detail", {
        gameid = gameid,
        lang = LAN:getLanguage(),
    }, function(d)
        if 0 == d.code then
            if cb then cb(true, d.data) end
        else
            if cb then cb(false) end
        end
    end)
end

-- 根据 listType 获取对应的列表数据
---@param listType string "recent" | "collect"
---@return table
function P:_getListByType(listType)
    if listType == "recent" then
        return self.recentList
    elseif listType == "collect" then
        return self.collectList
    end
    return nil
end

-- 查找 gameid 在指定列表中的位置 (内部用)
---@param gameid string
---@param listType string "recent" | "collect"
---@return table|nil {list, index}
function P:_findGameidInList(gameid, listType)
    local list = self:_getListByType(listType)
    if not list then
        return nil
    end
    for i, v in ipairs(list) do
        if v.gameid == gameid then
            return {list = list, index = i}
        end
    end
    return nil
end

--- 在指定列表中查找 gameid 的相邻位置
---@param gameid string 当前牌局ID
---@param direction string "prev" | "next"
---@param listType string "recent" | "collect"
---@return table|nil {gameid, index}
function P:getAdjacentGameid(gameid, direction, listType)
    local pos = self:_findGameidInList(gameid, listType)
    if not pos then
        return nil
    end
    local targetIdx
    if direction == "prev" then
        targetIdx = pos.index - 1
    else
        targetIdx = pos.index + 1
    end
    if targetIdx >= 1 and targetIdx <= #pos.list then
        return {
            gameid = pos.list[targetIdx].gameid,
            index = targetIdx,
            game_start_time = pos.list[targetIdx].game_start_time,
        }
    end
    return nil -- 在列表中但已在边界
end

--- 是否有上一局 (列表按时间倒序，index-1 即更新的记录)
---@param gameid string
---@param listType string "recent" | "collect"
---@return boolean
function P:hasPrevDetail(gameid, listType)
    local pos = self:_findGameidInList(gameid, listType)
    if not pos then
        return false
    end
    return pos.index > 1
end

--- 是否有下一局 (本地列表有下一项，或列表边界但服务端还有更多数据)
---@param gameid string
---@param listType string "recent" | "collect"
---@return boolean
function P:hasNextDetail(gameid, listType)
    local pos = self:_findGameidInList(gameid, listType)
    if not pos then
        return false
    end
    -- 本地列表中有下一项
    if pos.index < #pos.list then
        return true
    end
    -- 在列表末尾：检查服务端是否还有更多
    if listType == "recent" then
        return self:hasMoreRecent()
    elseif listType == "collect" then
        return self:hasMoreCollect()
    end
    return false
end

--- 获取相邻牌局详情 (上一局 / 下一局)
---@param gameid string 当前牌局ID
---@param direction string "prev" | "next"
---@param listType string "recent" | "collect"
---@param cb function 回调 function(success, detailData, adjacentGameid)
function P:fetchAdjacentDetail(gameid, direction, listType, cb)
    local adjacent = self:getAdjacentGameid(gameid, direction, listType)

    if adjacent then
        -- 本地列表找到了相邻 gameid
        self:fetchGameDetail(adjacent.gameid, function(ok, detail)
            if cb then
                detail.game_start_time = adjacent.game_start_time
                cb(ok, detail, adjacent.gameid)
            end
        end)
        return
    end

    -- 本地没找到，尝试从服务端加载更多
    if listType == "recent" and direction == "next" then
        if self:hasMoreRecent() then
            self:fetchMoreRecent(function(ok)
                if ok then
                    local retry = self:getAdjacentGameid(gameid, direction, listType)
                    if retry then
                        self:fetchGameDetail(retry.gameid, function(ok2, detail)
                            if cb then
                                detail.game_start_time = retry.game_start_time
                                cb(ok2, detail, retry.gameid)
                            end
                        end)
                        return
                    end
                end
                if cb then cb(false) end
            end)
            return
        end
    elseif listType == "collect" and direction == "next" then
        if self:hasMoreCollect() then
            self:fetchMoreCollect(function(ok)
                if ok then
                    local retry = self:getAdjacentGameid(gameid, direction, listType)
                    if retry then
                        self:fetchGameDetail(retry.gameid, function(ok2, detail)
                            if cb then
                                detail.game_start_time = retry.game_start_time
                                cb(ok2, detail, retry.gameid)
                            end
                        end)
                        return
                    end
                end
                if cb then cb(false) end
            end)
            return
        end
    end

    -- 已到边界，无法加载更多
    if cb then cb(false) end
end

--- 获取上一局详情 (便捷方法)
---@param gameid string
---@param listType string "recent" | "collect"
---@param cb function
function P:fetchPrevDetail(gameid, listType, cb)
    self:fetchAdjacentDetail(gameid, "prev", listType, cb)
end

--- 获取下一局详情 (便捷方法)
---@param gameid string
---@param listType string "recent" | "collect"
---@param cb function
function P:fetchNextDetail(gameid, listType, cb)
    self:fetchAdjacentDetail(gameid, "next", listType, cb)
end

-- ============================== 工具方法 ==============================

--- 根据 gameid 在本地缓存中查找记录
---@param gameid string
---@return table|nil
function P:findRecord(gameid)
    for _, v in ipairs(self.collectList) do
        if v.gameid == gameid then
            return v
        end
    end
    if self._allCollects[gameid] then
        return self._allCollects[gameid]
    end
    for _, v in ipairs(self.recentList) do
        if v.gameid == gameid then
            return v
        end
    end
    return nil
end

function P:isRecentLoading()
    return self._recentLoading
end

function P:isCollectLoading()
    return self._collectLoading
end

-- ============================== 生命周期 ==============================

function P:clear()
    self:resetRecent()
    self:resetCollect()
end

function P:evt_lan_mod()
    self:markRecentDirty()
    self:markCollectDirty()
end

return P