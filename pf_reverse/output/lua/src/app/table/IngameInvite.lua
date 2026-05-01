local P = class("IngameInvite", UiBase)

function P:onAwake()
    self.Right = self:find("AnimRoot/Right")

    self.SidePanel = self:find("SidePanel", self.Right)

    self.FriendsList = self:find("FriendsList", self.SidePanel)
    self.Item1 = self:find("Item1", self.FriendsList)
    self.Item1:SetActive(false)
    self.Empty = self:find("Empty", self.SidePanel)

    bee.addClick(self:find("SideButton", self.SidePanel), function()
        self:hideUI()
    end)
    bee.addClick(self:find("Mask"), function()
        self:hideUI()
    end)
    bee.addClick(self:find("CopyButton", self.SidePanel), function()
        CS.SdkHelper.copyText(G_SHARE_URL .. "?kind=friendsgame&nickname=" .. PlayerModel:getName() .. "&room_num=" .. GameModel.data:getRoomId() .. "&cid=" .. G_CHNL_ID)
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)

    self.ListFriends = UiListEx:create(self.FriendsList)
    self.ListFriends:setWidth(180)
    self.ListFriends:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListFriends:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)
end

function P:onShow()
    self.FriendsList:SetActive(false)
    self.Empty:SetActive(true)

    FriendModel:getOnlineFriends(function(friends)
        local datas = {}
        local roomId = GameModel.data:getRoomId()
        for _, v in ipairs(friends) do
            if v.roomid ~= roomId then
                table.insert(datas, v)
            end
        end
        self.FriendsList:SetActive(#datas > 0)
        self.Empty:SetActive(#datas == 0)
        self.ListFriends:setDatas(datas)
    end)
end

function P:refreshItem(data, item)
    local name = data.mark
    if not name or name == "" then
        name = data.nickname
    end
    bee.setTextCut(self:find("TextName", item), name, 215)
    bee.setText(self:find("Rank/TextLevel", item), data.level)
    if data.level > 0 then
        bee.setIcon(self:find("Rank/icon_rank_01", item), tpl_level[data.level].icon)
    end
    bee.setIcon(self:find("Avatar/Mask/ImageIcon", item), PlayerModel:getAvatarIcon(data.avatar))
    GF.setTitleImage(self:find("ImageTitle", item), data.using_title)
    GF.setFrameImage(self:find("Avatar/ImageFrame", item), data.using_frame)
    if data.is_online and data.roomid == 0 then
        self:find("TextIngame", item):SetActive(false)
        self:find("TextOnline", item):SetActive(true)
    else
        self:find("TextIngame", item):SetActive(true)
        self:find("TextOnline", item):SetActive(false)
    end

    local InviteButton = self:find("InviteButton", item)
    local InvitedButton = self:find("InvitedButton", item)

    self:startInviteCD(InviteButton, InviteButton, InvitedButton, SettingModel:getKeyCD("invite_" .. data.uid), item)
    bee.addClick(InviteButton, function()
        if InviteButton.activeSelf then
            Net:sendReq("pb.InvitePlayREQ", {
                to_uid = data.uid,
            })

            self:startInviteCD(InviteButton, InviteButton, InvitedButton, 30, item)
            bee.logEvent("friendsroom-invite", GameModel.data:getRoomId(), PlayerModel:getUid(), data.uid)
        end
    end)
end

function P:startInviteCD(InviteButton, InviteButtonOn, InviteButtonOff, dt, item)
    scheduler:removeTarget(InviteButton)

    if dt and dt > 0 then
        InviteButtonOn:SetActive(false)
        InviteButtonOff:SetActive(true)
        bee.setText(self:find("TextTime", item), _F("LAB_FRIROOM_009", dt))
        bee.schedule(1, function()
            dt = dt - 1
            if dt <= 0 then
                scheduler:removeTarget(InviteButton)
                bee.setText(self:find("TextTime", item), "")
                InviteButtonOn:SetActive(true)
                InviteButtonOff:SetActive(false)
            else
                bee.setText(self:find("TextTime", item), _F("LAB_FRIROOM_009", dt))
            end
        end, InviteButton)
    else
        InviteButtonOn:SetActive(true)
        InviteButtonOff:SetActive(false)
        bee.setText(self:find("TextTime", item), "")
    end
end

function P:evt_InvitePlayRSP(msg)
    SettingModel:setKeyCD("invite_" .. msg.to_uid, 30)
end

return P