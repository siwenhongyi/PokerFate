local P = class("FriendsRoomList", UiDialog)

function P:onAwake()
    self.AnimRoot = self:find("AnimRoot")
    self.Panel = self:find("Center/Panel", self.AnimRoot)
    
    self.HistoryList = self:find("PiyoList", self.Panel)
    self.Item1 = self:find("Item1", self.HistoryList)
    self.Item1:SetActive(false)

    self.Empty = self:find("Empty", self.Panel)
    self.Filter = self:find("Filter", self.Panel)
    self.FilterArea = self:find("FilterArea", self.Filter)
    self.FilterItem = self:find("FilterItem", self.Filter)
    self.TextFilter = self:find("TextFilter", self.Filter)
    self.FilterMask = self:find("FilterMask", self.Filter)
    self.FilterArea:SetActive(false)
    self.FilterItem:SetActive(false)
    self.FilterMask:SetActive(false)

    self.CheckToggle = self:find("CheckToggle", self.Panel)

    bee.addClick(self:find("RefreshButton", self.Panel), function()
        Game:playSound("ui_button_confirm")
        Net:sendReq("pb.FriendRoomListREQ", {})
        bee.logEvent("friendsroom-room-list-refresh")
    end)
    bee.addClick(self:find("CloseButton", self.Panel), function()
        self:hideUI()
    end)
    bee.addClick(self.Filter, function()
        Game:playSound("ui_button_confirm")
        self:setFilterShow()
    end)
    bee.addValueChanged(self.CheckToggle, function(isOn)
        Game:playSound("ui_button_disabled")
        self:refreshList()
        bee.logEvent("friendsroom-room-list-filter", isOn and 1 or 2)
    end)

    self.ListHistory = UiListEx:create(self.HistoryList)
    self.ListHistory:setWidth(220)
    self.ListHistory:setCreateFunc(function(data)
        return CU.GameObject.Instantiate(self.Item1)
    end)
    self.ListHistory:setRefreshFunc(function(data, item)
        self:refreshItem(data, item)
    end)
end

function P:onShow()
    self._filterIdx = 1
    self:setFilterText(self.TextFilter, self._filterIdx)

    self._datas = {}
    self.Empty:SetActive(true)
    self.HistoryList:SetActive(false)
    Net:sendReq("pb.FriendRoomListREQ", {})

    bee.logEvent("friendsroom-room-list")
end

function P:refreshList()
    local datas = {}
    local showFull = not bee.isCheck(self.CheckToggle)
    for _, v in ipairs(self._datas) do
        if (showFull or v.sited_num < v.seat_num) and (1 == self._filterIdx or v.seat_num == self._filterIdx) then
            table.insert(datas, v)
        end
    end
    self.Empty:SetActive(0 == #datas)
    self.HistoryList:SetActive(#datas > 0)
    self.ListHistory:setDatas(datas)
end

function P:setFilterShow()
    local flag = self.FilterArea.activeSelf
    self.FilterArea:SetActive(not flag)
    self.FilterMask:SetActive(not flag)
    self:find("common_panel_black_filter_arrow_1", self.Filter):SetActive(flag)
    self:find("common_panel_black_filter_arrow_2", self.Filter):SetActive(not flag)
    if not flag and not self._initFilter then
        self._initFilter = true
        self._filterItems = {}
        for i = 1, 6 do
            local item = CU.GameObject.Instantiate(self.FilterItem, self.FilterArea.transform, false)
            self._filterItems[i] = item
            item:SetActive(true)
            self:setFilterText(self:find("On/TextNum", item), i)
            self:setFilterText(self:find("Off/TextNum", item), i)
            self:find("On", item):SetActive(self._filterIdx == i)
            self:find("Off", item):SetActive(self._filterIdx ~= i)
            bee.addClick(item, function()
                Game:playSound("ui_button_confirm")
                if i ~= self._filterIdx then
                    self._filterIdx = i
                    self:setFilterText(self.TextFilter, self._filterIdx)
                    self:refreshList()
                end
                self.FilterArea:SetActive(false)
                self.FilterMask:SetActive(false)
                self:find("common_panel_black_filter_arrow_1", self.Filter):SetActive(true)
                self:find("common_panel_black_filter_arrow_2", self.Filter):SetActive(false)
                bee.logEvent("friendsroom-room-list-seat", self._filterIdx)
            end)
        end
    elseif not flag then
        for i, item in ipairs(self._filterItems) do
            self:find("On", item):SetActive(self._filterIdx == i)
            self:find("Off", item):SetActive(self._filterIdx ~= i)
        end
    end
end

function P:setFilterText(obj, idx)
    if idx == 1 then
        bee.setText(obj, _T("LAB_FRIROOM_034"))
    else
        bee.setText(obj, _F("LAB_FRIROOM_020", idx))
    end
end

function P:refreshItem(data, item)
    bee.setTextCut(self:find("TextName", item), data.owner.name, 217)
    bee.setIcon(self:find("Mask/ImageIcon", item), PlayerModel:getAvatarIcon(data.owner.avatar))
    GF.setFrameImage(self:find("ImageFrame", item), data.owner.frame)

    bee.setText(self:find("Blind/TextBlind", item), _N(data.bb / 2) .. "/" .. _N(data.bb))
    bee.setText(self:find("Buyin/TextByin", item), _N(data.min_byin) .. "-" .. _N(data.max_byin))

    self:find("common_panel_blue_tag_01_a", item):SetActive(data.sited_num <= 1)
    self:find("common_panel_blue_tag_01_b", item):SetActive(data.sited_num > 1)

    local JoinButton = self:find("JoinButton", item)
    local FullButton = self:find("FullButton", item)
    local s = string.format("%d/%d", data.sited_num, data.seat_num)
    if data.sited_num >= data.seat_num then
        self:find("TextNum1", item):SetActive(false)
        self:find("TextNum2", item):SetActive(true)
        bee.setText(self:find("TextNum2", item), s)
        JoinButton:SetActive(false)
        FullButton:SetActive(true)
    else
        self:find("TextNum1", item):SetActive(true)
        self:find("TextNum2", item):SetActive(false)
        bee.setText(self:find("TextNum1", item), s)
        JoinButton:SetActive(true)
        FullButton:SetActive(false)
    end

    bee.addClick(JoinButton, function()
        Game:playSound("ui_button_confirm")
        if data.sited_num < data.seat_num then
            Net:sendReq("pb.JoinFriendRoomREQ", {
                roomid = tonumber(data.roomid),
            })
	        SettingModel:addTag("friends_enter_toast")
        end
    end, true)
end

function P:evt_FriendRoomListRSP(msg)
    self._datas = msg.room_list
    self:refreshList()
end

