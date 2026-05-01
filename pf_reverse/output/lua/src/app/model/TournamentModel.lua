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
end

function P:afterLogin()
    -- if not self.cloud["reads" .. PlayerModel:getUid()] then
    --     self.cloud["reads" .. PlayerModel:getUid()] = {}
    -- end
    -- self._reads = self.cloud["reads" .. PlayerModel:getUid()]
end

function P:refreshReddot()
end

function P:setByinText(Text, sign_item, showRed)
    if sign_item and sign_item.item_num > 0 then
        if showRed and sign_item.item_num > ItemModel:getItemNumById(sign_item.item_id) then
            bee.setText(Text, _F("<color=#FF4747>{p1}</color>", _N(sign_item.item_num)))
        else
            bee.setText(Text, _N(sign_item.item_num))
        end
    else
        bee.setText(Text, _T("LAB_SHOP_COMMON_21") .. "  ")
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

-- req_type: 0 所有 1 SNG 2 MTT
function P:reqHistoryList(req_type, cb)
    self._historyCb = cb
    self._historyType = req_type
    self.room_start_time = 0
    Net:sendReq("pb.TourHistoryListREQ", {req_type = req_type, room_start_time = 0, lang = LAN:getLanguage()})
end

function P:reqNextHistoryList(req_type, cb)
    self._historyCb = cb
    self._historyType = req_type
    local room_start_time = 0
    if self.historys[req_type] and #self.historys[req_type] > 0 then
        room_start_time = self.historys[req_type][#self.historys[req_type]].room_start_time
    end
    if room_start_time > 0 and self._room_start_time ~= room_start_time then
        self._room_start_time = room_start_time
        Net:sendReq("pb.TourHistoryListREQ", {req_type = req_type, room_start_time = room_start_time, lang = LAN:getLanguage(), is_next_page = true})
    end
end

function P:evt_TourListRSP(msg)
    self.dataLists[msg.req_type] = msg.sng_list
    if self._reqCb and msg.req_type == self._reqType then
        self._reqCb(msg.sng_list, msg.history_sng_list)
    end
end

function P:evt_TourHistoryListRSP(msg)
    self.historys[msg.req_type] = msg.history_sng_list
    if self._historyCb and msg.req_type == self._historyType then
        self._historyCb(msg.history_sng_list)
    end
end

function P:reqSngSign(data, sign_item_id, cb)
    if not bee.checkCd("TOURNAMENT_MODEL_REQ_SNG_SIGN_" .. data.tour_id, 1) then
        return
    end
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
        if cb then
            cb(ret)
        end
        -- UiManager:showToast(_T("LAB_TOURNAMENT_SNG_INFO18"))
    end)
end

function P:reqMttSign(data, sign_item_id, cb)
    if not bee.checkCd("TOURNAMENT_MODEL_REQ_MTT_SIGN_" .. data.tour_id, 1) then
        return
    end
    Net:sendReq("pb.MttSignREQ", {
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
        if cb then
            cb(ret)
        end
        -- UiManager:showToast(_T("LAB_TOURNAMENT_SNG_INFO18"))
    end)
end

return P