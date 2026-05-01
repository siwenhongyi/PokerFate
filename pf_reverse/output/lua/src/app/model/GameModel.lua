---@class GameModel
local P = class("GameModel", BaseModel)

function P:ctor()
    self.saveData = {
        cloud = {},
    }

    P.super.ctor(self)

    self.data = nil
    self.layer = nil
    self.roomid = 0
    self.bb = 0

    self.bond_settle_info = nil -- 退出房间时好感度变化信息
    self.over_bond_settle_info = nil -- 退出房间时好感度变化信息

    self.gameType = 0
    self.roomId = 0

    self.selectRoomGameType = 0 -- 选择房间时的游戏类型

    self.stopGameMsg = nil -- 断线重连时服务器发送的暂停游戏消息

    self._stopMsgs = {
        ["pb.ActionNotifyBRC"] = true,
        ["pb.RoundStartBRC"] = true,
        ["pb.RoundOverBRC"] = true,
        ["pb.HandCardRSP"] = true,
        ["pb.PreActionRSP"] = true,
        ["pb.PreActionResetRSP"] = true,
        ["pb.WinnerRSP"] = true,
        ["pb.ShowHandRSP"] = true,
        ["pb.DealerInfoRSP"] = true,
        ["pb.ChipsBackBRC"] = true,
        ["pb.CancelWaitBlindBRC"] = true,
        ["pb.RebyBRC"] = true,
        ["pb.NoticeRebyRSP"] = true,
        ["pb.ActionRSP"] = true,
        ["pb.ActionBRC"] = true,
        ["pb.GetCardsRSP"] = true,
        ["pb.AnteBRC"] = true,
        ["pb.RoundStartDisplayFinishRSP"] = true,

        ["pb.StandUpRSP"] = true,
        ["pb.StandUpBRC"] = true,
        ["pb.SitDownRSP"] = true,
        ["pb.SitDownBRC"] = true,
        ["pb.FaceBRC"] = true,
        ["pb.TextRSP"] = true,
        ["pb.TextBRC"] = true,
        ["pb.CustomTextBRC"] = true,

        ["pb.SngSpinBRC"] = true,
    }
end

function P:afterLogin()
    self.stopGameMsg = nil
    GameModel.summary = nil
end

function P:setData(data, layer)
    self.data, self.layer = data, layer
    if self.data then
        self.gameType = self.data:getGameType()
        self.roomId = self.data:getRoomId()
        self.bb = self.data:getBigBlind()
    end
end

function P:getBigBlind()
    return self.bb
end

function P:getReplayTitle(data)
    local subTitle = _N(data.small_blind) .. "/" .. _N(data.big_blind)
    if data.tour_name and "" ~= data.tour_name then
        return data.tour_name .. "-" .. subTitle .. "-" .. TimeHelp:getDateTimeStr(data.game_start_time)
    end
    if GF.isTrainingGame(data.game_type) then
        subTitle = _T("LAB_GAME_053")
    end
    return GF.getGameTypeName(data.game_type) .. "-" .. subTitle .. "-" .. TimeHelp:getDateTimeStr(data.game_start_time)
end

function P:getReplayList(cb)
    Net:post("/collCard/list", {t = 1, lang = LAN:getLanguage()}, function(data)
        if 0 == data.code then
            if data.list then
                PlayerModel:setCurRecord(data.total)
            else
                PlayerModel:setCurRecord(0)
            end
        end
        if cb then cb(data) end
    end)
end

function P:deleteReplay(gameid, cb)
    Net:post("/collCard/update", {
        del_id = gameid,
    }, function(d)
        if 0 == d.code then
            PlayerModel:setCurRecord(#d.gameids)
        end
        if cb then cb(d) end
    end)
end

function P:reqGetRoomDataREQ()
    if self.data then
        Net:sendReq("pb.GetRoomDataREQ", {roomid = self.data:getRoomId()})
        self.stopGameMsg = true
    end
end

function P:isStopGameMsg(name)
    if self.stopGameMsg then
        return self._stopMsgs[name] == true
    end
    return false
end

function P:isStopLeaveRoom()
    return self._isStopLeaveRoom
end

function P:setStopLeaveRoom(flag)
    self._isStopLeaveRoom = flag
end

function P:getAllinUiName(item_id)
    if not item_id then
        item_id = PlayerModel:getAllInEff()
    end
    if tpl_props[item_id] then
        return tpl_all_in_anim[tpl_props[item_id].mapId].eff
    end
    return "IngameAllin"
end

function P:getAllinEffectName(kind, item_id)
    if not item_id then
        item_id = PlayerModel:getNameplateEff()
    end
    if kind > 3 then
        kind = 1
    end
    if tpl_props[item_id] then
        return tpl_nameplate_anim[tpl_props[item_id].mapId].eff .. "_" .. kind
    end
    return "Prefab/PKTable/Eff_Allin_fire_" .. "_" .. kind
end

function P:isAutoSwitchTable()
    local ret = self._isAutoSwitchTable
    self._isAutoSwitchTable = nil
    return ret
end

function P:switchTable(fromMenu)
    local info = GameModel.data:getMyPlayerInfo()
    if not info then
        return
    end
    local chips = info.chips
    if not GameModel.data:isAllinOrFold() then
        local data = GF.getTableDataBySB(GameModel.data:getGameType(), GameModel.data:getSmallBlind())
        if not data or chips < data.min_byin then
            if fromMenu then
                UiManager:showToast(_T("LAB_GAME_045"))
            end
            return
        end
    end
    self._isAutoSwitchTable = not fromMenu
    local d = {
        key = "switch_table",
        boot = GameModel.data:getBigBlind(), 
        game_type = GameModel.data:getGameType(),
        lobby_coin = GPropId.Gold,
        byin_chips = chips,
        default_byin = info.default_byin,
        wait_blind = not LocalStore:getBoolForKey("poker_pay_bb_byin", true),
        ip = PlayerModel:getIP(),
    }
    if GameModel.data:isPlaying() and GameModel.data:isMePlaying() and not GameModel.data:isMeFold() then
        UiManager:showTip({
            text = _T("LAB_GAME_047"),
            onSure = function()
                d.byin_chips = info.chips
                Net:sendReq("pb.LeaveRoomREQ", {
                    client_str = json.encode(d)
                })
            end
        })
        if fromMenu then
            bee.logEvent("ingame-menu-switch-ongoing", GameModel.data:getGameType(), GameModel.data:getRoomId())
        end
    else
        Net:sendReq("pb.LeaveRoomREQ", {
            client_str = json.encode(d)
        })
        if fromMenu then
            bee.logEvent("ingame-menu-switch-before", GameModel.data:getGameType(), GameModel.data:getRoomId())
        end
    end
end

return P