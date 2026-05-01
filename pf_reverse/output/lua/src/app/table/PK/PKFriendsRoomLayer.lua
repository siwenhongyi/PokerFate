local P = class("PKFriendsRoomLayer", require("app.table.PK.PKUILayer"))

function P:onAwake()
    P.super.onAwake(self)
    self.TextRoomType = self:find("RoomType/TextRoomType", self.LeftTop)
    self.TextNumber = self:find("RoomNumber/TextNumber", self.RightTop)
    
    bee.addClick(self:find("RoomNumber/CopyButton", self.RightTop), function()
        CS.SdkHelper.copyText("" .. GameModel.data:getRoomId())
        UiManager:showToast(_T("LAB_COPY_SUC"))
    end)
    bee.addClick(self:find("InviteButton", self.RightTop), function()
        UiManager:showUI("IngameInvite")
    end)
end

function P:onShow()
    P.super.onShow(self)

    self:refreshFriendRoomInfo()
    self.ChatButton:SetActive(not GameModel.data.friend_room_info.is_forbid_chat)
end

function P:refreshFriendRoomInfo()
    bee.setText(self.TextNumber, _F("LAB_FRIROOM_040", GameModel.data:getRoomId()))
    bee.setText(self.TextRoomType, GameModel.data.friend_room_info.is_private and _T("LAB_FRIROOM_005") or _T("LAB_FRIROOM_006"))
end

function P:evt_FriendRoomOwnerChangeBRC(msg)
    UiManager:showToast(_F("LAB_FRIROOM_045", msg.owner.name))
end

function P:evt_lan_mod()
    P.super.evt_lan_mod(self)
    self:refreshFriendRoomInfo()
end

return P