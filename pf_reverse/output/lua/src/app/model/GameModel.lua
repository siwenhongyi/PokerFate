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

function P:playUIEffect(name, parent, localPos, autoRemoveDt, noCache,layer)
    if self.layer then
        return self.layer:playUIEffect(name, parent, localPos, autoRemoveDt, noCache)
    end
    return nil
end

function P:putEffectItem(eft)
    if self.layer then
        self.layer:putEffectItem(eft)
    end
end

function P:getBigBlind()
    return self.bb
end

function P:getReplayTitle(data)
    local subTitle = _N(data.small_blind) .. "/" .. _N(data.big_blind)
    if (data.ante and data.ante ~= 0) then
        subTitle = subTitle .. " (" .. _N(data.ante) .. ")"
    end
    if data.tour_name and "" ~= data.tour_name then
        return data.tour_name .. "-" .. subTitle .. "-" .. TimeHelp:getDateTimeStr(data.game_start_time)
    end
    if GF.isTrainingGame(data.game_type) then
        subTitle = _T("LAB_GAME_053")
    end
    return GF.getGameTypeName(data.game_type, true) .. "-" .. subTitle .. "-" .. TimeHelp:getDateTimeStr(data.game_start_time)
end

function P:getReplayList(cb)
    RecordDataModel:fetchCollectList(nil, function(ok, list, total)
        if ok then
            PlayerModel:setCurRecord(total or 0)
        end
        if cb then cb({code = ok and 0 or -1, list = list, total = total}) end
    end)
end

function P:saveReplay(gameid, cb, roomid, tid)
    if PlayerModel:getCurRecord() >= PlayerModel:getRecordNum() then
        GameModel:getReplayList(function(d)
            if 0 == d.code then
                if d.list and #d.list > 0 then
                    local delData = d.list[#d.list]
                    UiManager:showTip({
                        text = _F("LAB_DEL_PLAYBACK_TIP5", GameModel:getReplayTitle(delData)),
                        sureStr = _T("LAB_SAVE"),
                        cancelStr = _T("LAB_DEL_PLAYBACK_TIP6"),
                        onSure = function()
                            RecordDataModel:replaceCollect(delData.gameid, gameid, function(ok)
                                if cb then cb(ok, delData.gameid) end
                            end, roomid, tid)
                        end,
                        onCancel = function()
                        end,
                    })
                end
            end
        end)
    else
        RecordDataModel:addCollect(gameid, function(ok)
            if cb then cb(ok) end
        end, roomid, tid)
    end
end

function P:deleteReplay(gameid, cb)
    RecordDataModel:removeCollect(gameid, cb)
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
        local scheme = DecorationModel:getInGameCurScheme()
        item_id = scheme.all_in_animation
    end
    if tpl_props[item_id] then
        return tpl_all_in_anim[tpl_props[item_id].mapId].eff
    end
    return "IngameAllin"
end

function P:getAllinEffectName(kind, item_id)
    if not item_id then
        local scheme = DecorationModel:getInGameCurScheme()
        item_id = scheme.show_card
    end
    if kind > 3 then
        kind = 1
    end
    local eff_bg = nil
    if tpl_props[item_id] then
        local d = tpl_nameplate_anim[tpl_props[item_id].mapId]
        if d.eff_bg then
            eff_bg = d.eff_bg .. "_" .. kind
        end
        return d.eff .. "_" .. kind, eff_bg
    end
    return "Prefab/PKTable/Eff_Allin_fire" .. "_" .. kind, eff_bg
end

function P:getAllinShowName(item_id)
    if item_id then
        local d = tpl_props[item_id]
        if d and tpl_open_anim[d.mapId] then
            return tpl_open_anim[d.mapId].eff
        end
    end
    return tpl_open_anim_list[1].eff
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
        scheme = GameModel.data:getIngameScheme(),
    }
    d.scheme.role_id = tpl_character_skin[d.scheme.skin_id].role
    if GameModel.data:isPlaying() and GameModel.data:isMePlaying() and not GameModel.data:isMeFold() then
        -- UiManager:showTip({
        --     text = _T("LAB_GAME_047"),
        --     onSure = function()
        --         d.byin_chips = info.chips
        --         Net:sendReq("pb.LeaveRoomREQ", {
        --             client_str = json.encode(d)
        --         })
        --     end
        -- })
        UiManager:showToast(_T("LAB_GAME_090"))
        if fromMenu then
            bee.logEvent("ingame-menu-switch-ongoing", GameModel.data:getGameType(), GameModel.data:getRoomId())
        end
    else
        Net:sendReq("pb.LeaveRoomREQ", {
            client_str = json.encode(d),
            is_switch_room = true,
        })
        if fromMenu then
            bee.logEvent("ingame-menu-switch-before", GameModel.data:getGameType(), GameModel.data:getRoomId())
        end
    end
end

function P:playSitdownVoice(skin_id)
    local skin = tpl_character_skin[skin_id]
    if skin and not self.data:isSNG() and not self.data:isMTT() and not self.data:isFriendSNG() then
        if skin.kind == SKIN_KIND.AWAKEN then
            Game:playRoleInVoice(skin.role, ROLE_VOICE.take_a_seat_awakened)
        elseif skin.kind == SKIN_KIND.SECOND_AWAKEN then
        	Game:playRoleInVoice(skin.role, ROLE_VOICE.take_a_seat_awakened2)
        else
            local voice_id = ROLE_VOICE.take_a_seat
            if skin.kind ~= SKIN_KIND.NORMAL then
                local ds = get_tpl_subKey(tpl_chat_list, "role", skin.role)
                for _, v in ipairs(ds) do
                    if v.skin_voice == skin_id and v.key == ROLE_VOICE.take_a_seat_skin then
                        voice_id = v.key
                        break
                    end
                end
            end
            Game:playRoleInVoice(skin.role, voice_id)
        end
    end
end

return P