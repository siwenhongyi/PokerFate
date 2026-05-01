local P = class("FriendsRoom", UiFullView)
local ROOM_ID_LIMIT = 6

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Center = self:find("Center", self.AnimRoot)
    self.RightTop = self:find("RightTop", self.AnimRoot)
    self.LeftTop = self:find("LeftTop", self.AnimRoot)

    self.Create = self:find("Create", self.Center)
    self.CreateButton = self:find("CreateButton", self.Center)

    self.Join = self:find("Join", self.Center)
    self.TextInputTip = self:find("TextInputTip", self.Join)
    self.TextInput = self:find("TextInput", self.Join)

    for i = 0, 9 do
        bee.addClick(self:find(string.format("Number%dButton", i), self.Join), function()
            Game:playSound("ui_button_confirm")
            self:addRoomNum(i)
        end)
    end
    bee.addClick(self:find("ClearButton", self.Join), function()
        if "" == self._curRoomId then
            UiManager:showToast(_T("LAB_FRIROOM_015"))
            return
        end
        Game:playSound("ui_button_confirm")
        self._curRoomId = ""
        self:refreshInput()
    end)
    bee.addClick(self:find("DeleteButton", self.Join), function()
        if #self._curRoomId > 0 then
            self._curRoomId = string.sub(self._curRoomId, 1, #self._curRoomId - 1)
            self:refreshInput()
            Game:playSound("ui_button_confirm")
        else
            UiManager:showToast(_T("LAB_FRIROOM_015"))
        end
    end)
    bee.addClick(self:find("JoinButton", self.Join), function()
        if #self._curRoomId < ROOM_ID_LIMIT then
            UiManager:showToast(_T("LAB_FRIROOM_025"))
            return
        end
        Game:playSound("ui_button_confirm")
        Net:sendReq("pb.JoinFriendRoomREQ", {
            roomid = tonumber(self._curRoomId),
        })
        bee.logEvent("friendsroom-join")
    end)

    bee.addClick(self.CreateButton, function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("FriendsRoomCreate")
        bee.logEvent("friendsroom-create")
    end)

    bee.addClick(self:find("ListButton", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("FriendsRoomList")
    end)
    bee.addClick(self:find("SettingButton", self.RightTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("Setting")
        bee.logEvent("friendsroom-setting")
    end)
    bee.addClick(self:find("InfoButton", self.LeftTop), function()
        Game:playSound("ui_button_confirm")
        UiManager:showUI("IngameRules")
        bee.logEvent("friendsroom-rules")
    end)

    bee.addClick(self:find("BackButton", self.LeftTop), function()
        self:hideUI()
    end)
end

function P:onShow()
    self._curRoomId = ""
    self:refreshInput()
end

function P:addRoomNum(i)
    if #self._curRoomId < ROOM_ID_LIMIT then
        self._curRoomId = self._curRoomId .. i
        self:refreshInput()
    end
end

function P:refreshInput()
    bee.setText(self.TextInput, self._curRoomId)
    self.TextInputTip:SetActive(#self._curRoomId == 0)
end

return P