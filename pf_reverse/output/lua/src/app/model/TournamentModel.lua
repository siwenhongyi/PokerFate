local P = class("TournamentModel", BaseModel)

function P:ctor()
    self.saveData = {
        cloud = {
            -- reads .. uid = {},
        }
    }

    P.super.ctor(self)

    self.LIST_TYPE = {
        My = 1,
        SNG = 2,
        MTT = 3,
    }

    self.HISTORY_TYPE = {
        All = 1,
        SNG = 2,
        MTT = 3,
    }

    self.dataLists = {
        [self.LIST_TYPE.My] = nil,
        [self.LIST_TYPE.SNG] = nil,
        [self.LIST_TYPE.MTT] = nil,
    }
    self.historys = {
        [self.HISTORY_TYPE.All] = nil,
        [self.HISTORY_TYPE.SNG] = nil,
        [self.HISTORY_TYPE.MTT] = nil,
    }

    self._haveNew = nil
    self._curLan = nil
    self._reads = nil

    self.sng_matching_roomid = 0
    self.sng_matching_num = 0
    self.sng_matching_name = {}
    self.sng_matching_tour_id = 0
end

function P:afterLogin()
    -- if not self.cloud["reads" .. PlayerModel:getUid()] then
    --     self.cloud["reads" .. PlayerModel:getUid()] = {}
    -- end
    -- self._reads = self.cloud["reads" .. PlayerModel:getUid()]
end

function P:showAddon()
    local ui = GameModel.layer
    local zOrder = ui and ui.uiLayer and (ui.uiLayer.zOrder + 5) or nil
	UiManager:showUI("TournamentMTTAddOn", {zOrder = zOrder})
end

function P:refreshReddot()
end

function P:refreshMatchingTip()
    if self.sng_matching_num > 0 then
        if bee.isInHome() or (bee.isInGame() and GameModel.data and (not GameModel.data:isSNG() or GameModel.data:isRecord() or GameModel.data:isInObserve())) then
            local ui = UiManager:getUI("TournamentSNGhint")
            if not ui then
                UiManager:showUI("TournamentSNGhint")
            end
        end
    else
        UiManager:hideUIForce("TournamentSNGhint")
    end
end

function P:setMatchingSngInfo(roomid, num, name, tour_id)
    self.sng_matching_roomid = roomid
    self.sng_matching_num = num
    self.sng_matching_name = name
    self.sng_matching_tour_id = tour_id or 0
end

function P:getMatchingSngName()
    if self.sng_matching_name then
        for _, v in ipairs(self.sng_matching_name) do
            if v.lang == LAN:getLanguage() then
                return v.text
            end
        end
    end
    return ""
end

function P:isMttData(data)
    return data.isMtt
end

function P:isCanEnterMTT(data)
    return data.tour_status ~= TOUR_STATUS.Finished and data.enter_room_time <= bee.getServerTime() and self:isRegister(data)
end

function P:isInSignStatus(data)
    return data.sign_status == MTT_SIGN_STATUS.Inporcess or data.sign_status == MTT_SIGN_STATUS.Delayed
end

function P:isCanRegisterMTT(data)
    if data.tour_status == TOUR_STATUS.Finished then
        return false
    end
    local isInTime = data.sign_start_time <= bee.getServerTime() and data.sign_end_time >= bee.getServerTime() and self:isInSignStatus(data)
    if data.player_status == MTT_PLAYER_STATUS.Losed and isInTime and data.left_reby_times then
        return data.left_reby_times > 0 or data.left_reby_times == -1
    end
    return data.tour_status ~= TOUR_STATUS.Finished and self:isUnregister(data) and isInTime and data.cur_sign_num < data.max_player_num
end

function P:isCanUnregisterMTT(data)
    return data.tour_status ~= TOUR_STATUS.Finished and self:isRegister(data) and data.enter_room_time and data.enter_room_time > bee.getServerTime()
end

function P:isCanShowDetailMTT(data)
    return data.tour_status == TOUR_STATUS.Finished or data.player_status == MTT_PLAYER_STATUS.Losed or ((not self:isInSignStatus(data) or data.sign_end_time <= bee.getServerTime()) and data.player_status == MTT_PLAYER_STATUS.Unregister)
end

function P:isCanObserveMTT(data)
    if self:isCanShowDetailMTT(data) and data.tour_status ~= TOUR_STATUS.Finished then
        if data.player_status == MTT_PLAYER_STATUS.Losed or (data.player_status == MTT_PLAYER_STATUS.Unregister and data.sign_status ~= MTT_SIGN_STATUS.Unopen and (bee.getServerTime() >= data.sign_end_time or not self:isInSignStatus(data))) then
            return true
        end
    end
    return false
end

function P:isUnregister(data)
    if self:isMttData(data) then
        return data.player_status == MTT_PLAYER_STATUS.Unregister
    end
    return data.tour_status == TOUR_STATUS.Unregister
end

function P:isRegister(data)
    if self:isMttData(data) then
        return data.player_status == MTT_PLAYER_STATUS.Register
    end
    return data.tour_status == TOUR_STATUS.Register
end

function P:getSignItem(data)
    local signItem, itemData = nil, nil
    if data.sign_item and data.sign_item.item_id > 0 and tpl_props[data.sign_item.item_id] then
        return data.sign_item, ItemModel:getItem(data.sign_item.item_id, true)
    end
    if data.sign_item_list and #data.sign_item_list > 0 then
        for k, v in ipairs(data.sign_item_list) do
            itemData = ItemModel:getItem(v.item_id, true)
            if itemData.num >= v.item_num or k == #data.sign_item_list then
                signItem = v
                break
            end
        end
    end
    return signItem, itemData
end

function P:setByinTextByMttData(data, Text, Icon, showRed)
    local signItem, item = self:getSignItem(GameModel.data.room_info)
    self:setByinText(Text, signItem, showRed, Icon)
end

function P:setByinText(Text, sign_item, showRed, Icon)
    if sign_item and sign_item.item_num > 0 then
        if showRed and sign_item.item_num > ItemModel:getItemNumById(sign_item.item_id) then
            bee.setText(Text, _F("<color=#FF4747>{p1}</color>", _N(sign_item.item_num)))
        else
            bee.setText(Text, _N(sign_item.item_num))
        end
        if Icon then
            Icon:SetActive(true)
            bee.setIcon(Icon, tpl_props[sign_item.item_id].icon)
            bee.addClick(Icon, function()
                UiManager:showUI("CommonItemTip", {data = sign_item, target = Icon})
            end, true)
        end
    else
        bee.setText(Text, _T("LAB_SHOP_COMMON_21") .. "  ")
        if Icon then
            Icon:SetActive(false)
        end
    end
end

function P:isCanSign(sign_item_list)
    if #sign_item_list > 0 then
        for k, v in ipairs(sign_item_list) do
            local itemData = ItemModel:getItem(v.item_id, true)
            if itemData.num >= v.item_num then
                return true
            end
        end
        return false
    end
    return true
end

function P:reqTourList(listType, cb)
    self._reqCb = cb
    self._reqType = listType
    Net:sendReq("pb.TourListREQ", {req_type = listType, lang = LAN:getLanguage()})
end

function P:reqGetMttTourBriefInfoREQ(ids, cb, listType)
    listType = listType or self.LIST_TYPE.MTT
    if self.dataLists[listType] and #self.dataLists[listType] > 0 then
        if not ids then
            ids = {}
            for _, v in ipairs(self.dataLists[listType]) do
                table.insert(ids, v.tour_id)
            end
        end
        if #ids > 0 then
            Net:sendReq("pb.GetMttTourBriefInfoREQ", {tour_id_list = ids}, function(ret)
                if ret.code ~= 0 then
                    return
                end
                
                local flag = false
                local data = nil
                for _, v in ipairs(ret.briefs) do
                    table.removebyvalue(ids, v.tour_id)
                    for k, mtt in ipairs(self.dataLists[listType]) do
                        if mtt.tour_id == v.tour_id then
                            mtt.cur_sign_num = v.sign_num
                            if v.sign_status then
                                mtt.sign_status = v.sign_status
                            end
                            if v.tour_status then
                                mtt.tour_status = v.tour_status
                            end
                            flag = true
                            data = v
                            if mtt.tour_status == TOUR_STATUS.Finished then
                                table.remove(self.dataLists[listType], k)
                            end
                            break
                        end
                    end
                end
                for _, id in ipairs(ids) do
                    for k, mtt in ipairs(self.dataLists[listType]) do
                        if mtt.tour_id == id then
                            mtt.tour_status = TOUR_STATUS.Finished
                            if mtt.tour_status == TOUR_STATUS.Finished then
                                table.remove(self.dataLists[listType], k)
                            end
                            flag = true
                            if not data then
                                data = mtt
                            end
                            break
                        end
                    end
                end
                if flag and cb then
                    cb(data)
                end
            end)
        end
    end
end

-- req_type: 0 所有 1 SNG 2 MTT
function P:reqHistoryList(req_type, cb)
    self._historyCb = cb
    self._historyType = req_type
    self.room_start_time = 0
    self.historys[req_type] = {}
    Net:sendReq("pb.TourHistoryListREQ", {req_type = req_type, room_start_time = 0, lang = LAN:getLanguage()})
end

function P:reqNextHistoryList(req_type, cb)
    self._historyCb = cb
    self._historyType = req_type
    local room_start_time = 0
    if self.historys[req_type] and #self.historys[req_type] > 0 then
        local hd = self.historys[req_type][#self.historys[req_type]]
        room_start_time = hd.room_start_time or hd.mtt_start_time
    end
    if room_start_time > 0 and self._room_start_time ~= room_start_time then
        self._room_start_time = room_start_time
        Net:sendReq("pb.TourHistoryListREQ", {req_type = req_type, room_start_time = room_start_time, lang = LAN:getLanguage(), is_next_page = true})
    end
end

function P:evt_TourListRSP(msg)
    local list = nil
    for _, v in ipairs(msg.sng_list) do
        v.isSng = true
        v.__kind = 1
    end
    for _, v in ipairs(msg.mtt_list) do
        v.isMtt = true
        v.__kind = 2
    end
    if msg.req_type == self.LIST_TYPE.SNG then
        list = msg.sng_list
    elseif msg.req_type == self.LIST_TYPE.MTT then
        list = msg.mtt_list
    else
        list = table.merge_list(msg.sng_list, msg.mtt_list)
        table.sort(list, function(a, b)
            local t1 = a.room_start_time or a.mtt_start_time
            local t2 = b.room_start_time or b.mtt_start_time
            return t1 > t2
        end)
    end
    self.dataLists[msg.req_type] = list
    if self._reqCb and msg.req_type == self._reqType then
        self._reqCb(list)
    end
end

function P:evt_TourHistoryListRSP(msg)
    for _, v in ipairs(msg.history_sng_list) do
        v.isSng = true
        v.__kind = 1
    end
    for _, v in ipairs(msg.history_mtt_list) do
        v.isMtt = true
        v.__kind = 2
    end
    local list = nil

    if msg.req_type == self.HISTORY_TYPE.SNG then
        list = msg.history_sng_list
    elseif msg.req_type == self.HISTORY_TYPE.MTT then
        list = msg.history_mtt_list
    else
        list = table.merge_list(msg.history_sng_list, msg.history_mtt_list)
        table.sort(list, function(a, b)
            local t1 = a.room_start_time or a.mtt_start_time
            local t2 = b.room_start_time or b.mtt_start_time
            return t1 > t2
        end)
    end

    self.historys[msg.req_type] = table.merge_list(self.historys[msg.req_type] or {}, list)
    if self._historyCb and msg.req_type == self._historyType then
        self._historyCb(self.historys[msg.req_type])
    end
end

function P:reqSngSign(data, sign_item_id, cb)
    if not bee.checkCd("TOURNAMENT_MODEL_REQ_SNG_SIGN_" .. data.tour_id, 1) then
        return
    end
    if self.sng_matching_num > 0 and self.sng_matching_num < 3 then
        UiManager:showToast(_F("LAB_TOURNAMENT_SNG_INFO52", self:getMatchingSngName()))
        return
    end
    bee.logEvent("tournament-signup", 1, data.tour_id)
    Net:sendReq("pb.SngSignREQ", {
        tour_id = data.tour_id, 
        sign_item_id = sign_item_id, 
        -- game_type = data.game_type, 
        ip = PlayerModel:getIP()
    }, function(ret)
        if ret.code ~= 0 then
            if ret.code == tpl_RetCode.ERR_SNG_NOT_AVAILABLE.code then
                bee.emit(EventDef.evt_sng_not_available)
            end
            return
        end
        data.tour_status = TOUR_STATUS.Register
        bee.emit("evt_SngSign", {roomId = ret.roomid})
        if cb then
            cb(ret)
        end

        -- Net:sendReq("pb.SngMatchPlayerNumREQ", {})
        -- Net:sendReq("pb.EnterRoomREQ", {roomid = data.roomid})
        -- UiManager:showToast(_T("LAB_TOURNAMENT_SNG_INFO18"))
    end)
end

function P:reqSngCancelSign(roomId, gameType)
    Net:sendReq("pb.SngCancelSignREQ", {roomid = roomId, game_type = gameType})
end

function P:evt_SngCancelSignRSP(msg)
    if msg.code ~= 0 then
        return
    end

    if "" ~= msg.reason then
        local code = tonumber(msg.reason)
        if code then
            Net:onErrorCode({code = code})
        end
    end

    self:setMatchingSngInfo(0, 0, {}, 0)
    UiManager:hideUIForce("TournamentSNGhint")
    bee.emit("evt_CancelSngSign")
end

function P:reqMttSign(data, sign_item_id, cb)
    if not bee.checkCd("TOURNAMENT_MODEL_REQ_MTT_SIGN_" .. data.tour_id, 1) then
        return
    end
    if self.sng_matching_num > 0 and self.sng_matching_num < 3 and data.mtt_start_time and data.mtt_start_time <= bee.getServerTime() then
        UiManager:showToast(_F("LAB_TOURNAMENT_SNG_INFO52", self:getMatchingSngName()))
        return
    end
    bee.logEvent("tournament-signup", 2, data.tour_id)
    Net:sendReq("pb.MttSignREQ", {
        tour_id = data.tour_id, 
        sign_item_id = sign_item_id, 
        -- game_type = data.game_type, 
        multiple = data.multiple or 1,
        ip = PlayerModel:getIP(),
    }, function(ret)
        if ret.code ~= 0 then
            if ret.code == tpl_RetCode.ERR_SNG_NOT_AVAILABLE.code then
                bee.emit(EventDef.evt_sng_not_available)
            end
            return
        end
        data.player_status = MTT_PLAYER_STATUS.Register
        if 0 == ret.sign_type then
            data.cur_sign_num = (data.cur_sign_num or 0) + 1
        end
        if data.sign_item_list then
            for _, v in ipairs(data.sign_item_list) do
                if v.item_id == sign_item_id then
                    data.sign_item = v
                    break
                end
            end
        end
        
        if cb then
            cb(ret)
        end
        -- UiManager:showToast(_T("LAB_TOURNAMENT_SNG_INFO18"))
    end)
end

function P:reqMttCancelSign(data, cb)
    bee.logEvent("tournament-signup-cancel", 2, data.tour_id)
    Net:sendReq("pb.MttCancelSignREQ", {
        tour_id = data.tour_id, 
    }, function(ret)
        if ret.code ~= 0 then
            return
        end
        data.player_status = MTT_PLAYER_STATUS.Unregister
        data.cur_sign_num = (data.cur_sign_num or 1) - 1
        data.sign_item = nil
        if cb then
            cb(ret)
        end
        -- UiManager:showToast(_T("LAB_TOURNAMENT_SNG_INFO18"))
    end)
end

return P