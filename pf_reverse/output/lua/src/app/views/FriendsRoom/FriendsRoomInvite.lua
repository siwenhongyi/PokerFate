local P = class("FriendsRoomInvite", UiBase)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Notice = self:find("RightBottom/Notice", self.AnimRoot)

    self.TextTip = self:find("TextTip", self.Notice)
    self.TextTime = self:find("CancelButton/TextTime", self.Notice)

    self.common_panel_mask_70 = self:find("common_panel_mask_70", self.AnimRoot)

    bee.addClick(self:find("ConfirmButton", self.Notice), function()
        if GameModel.data and GameModel.data:isMePlaying() then
            UiManager:showTip({
                text = _T("LAB_SURE_EXIT"),
                onSure = function()
                    SettingModel:addTag("friends_enter_toast")
                    self:doEnterRoom()
                end,
            })
        else
            self:doEnterRoom()
        end
        self:hideUI()
    end)
    bee.addClick(self:find("CancelButton", self.Notice), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CloseButton", self.Notice), function()
        self:hideUI()
    end)
end

function P:onShow()
    self:refreshTime(10)
    local name = self._params.data.inviter_name
    local info = FriendModel:getFriendInfo(self._params.data.inviter_uid)
    if info and info.mark and info.mark ~= "" then
        name = info.mark
    end
    bee.setText(self.TextTip, _F("LAB_FRIROOM_036", name))
end

function P:refreshTime(dt)
    dt = math.ceil(dt)
    bee.setText(self.TextTime, string.format("(%s)", _F("LAB_FRIROOM_009", dt)))
    self:schedule(1, function()
        dt = dt - 1
        if dt <= 0 then
            self:hideUI()
            return
        end
        bee.setText(self.TextTime, string.format("(%s)", _F("LAB_FRIROOM_009", dt)))
    end)
end

function P:doEnterRoom()
    if GameModel.data and not GameModel.data:isRecord() then
        Net:sendReq("pb.LeaveRoomREQ", {
            client_str = json.encode({
                key = "invite",
                roomid = self._params.data.roomid,
            })
        })
    else
        Net:sendReq("pb.JoinFriendRoomREQ", {
            roomid = tonumber(self._params.data.roomid),
        })
    end
end

function P:evt_InvitePlayBRC(msg)
end

