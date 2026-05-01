local P = class("Friend", UiFullView)

local TabIndex = {
	FriendsList = 1,	-- 好友列表
	FindFriends = 2,	-- 查询好友
	ApplyList = 3,		-- 申请列表
	BlockedList = 4,	-- 黑名单
}

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	local LeftTop = self:find("LeftTop", self.AnimRoot)
	local Left = self:find("Left", self.AnimRoot)
	local Center = self:find("Center", self.AnimRoot)
	local Top = self:find("Top", self.AnimRoot)
	self.Bottom = self:find("Bottom", self.AnimRoot)

	self.Blank = self:find("Blank", Center)
	self.BlankTips = self:find("BlankTips", self.Blank)
	self.GoButton = self:find("GoButton", self.Blank)
	self.FullList = self:find("FullList", Center)
	self.HalfList = self:find("HalfList", Center)
	self.ItemPlayer = self:find("ItemPlayer", Center)
	self.ItemPlayer:SetActive(false)

	self.RecentList = self:find("RecentList", self.Bottom)
	self.RecentBlankTips = self:find("RecentBlankTips", self.Bottom)
	self.ItemRecentPlayer = self:find("ItemRecentPlayer", self.Bottom)
	self.ItemRecentPlayer:SetActive(false)

	self.InputFieldSearch = self:find("InputFieldSearch", Top)
	self.SearchButton = self:find("SearchButton", self.InputFieldSearch)
	self.ClearButton = self:find("ClearButton", self.InputFieldSearch)
	self.SelfIDText = self:find("UID/SelfIDText", Top)
	self.CopyButton = self:find("UID/CopyButton", Top)
	self.FriendsCountText = self:find("FriendsCount/FriendsCountText", Top)
	self.SearchButton:SetActive(true)
	self.ClearButton:SetActive(false)

	local TabToggle = self:find("TAB/TabToggle", Left)
	self.tabToggleList = {}
	for i = 1, 4 do
		table.insert(self.tabToggleList, self:find("TabToggle" .. i, TabToggle))
		bee.addValueChanged(self.tabToggleList[i], function(isOn)
			if isOn then
				if i ~= self._selectedIndex then
					Game:playSound("ui_tab_switch_1")
				end
				self:onClickTabToggle(i)
				if 1 == i then
					bee.logEvent("friends-main")
				elseif 2 == i then
					bee.logEvent("friends-search")
				elseif 3 == i then
					bee.logEvent("friends-requests")
				elseif 4 == i then
					bee.logEvent("friends-blacklist")
				end
			end
			if isOn then
			else
				self:playToggleIdle2(self.tabToggleList[i])
			end
		end)
	end

	local ApplyRedPoint = self:find("RedPoint", self.tabToggleList[TabIndex.ApplyList])
	RedManager:bind(ApplyRedPoint, RedTag.ApplyFriends)

	self.BackButton = self:find("BackButton", LeftTop)
	bee.addClick(self.BackButton, function()
		self:hideUI()
	end)

	bee.addClick(self.GoButton, function()
		Game:playSound("ui_button_confirm")
		bee.setCheck(self.tabToggleList[TabIndex.FindFriends])
		self:onClickTabToggle(TabIndex.FindFriends)
		bee.logEvent("friends-main-jump")
	end)
	bee.addClick(self.ClearButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickClearButton()
	end)
	bee.addClick(self.CopyButton, function()
		CS.SdkHelper.copyText("" .. PlayerModel:getUid())
        UiManager:showToast(_T("LAB_COPY_SUC"))
		bee.logEvent("friends-main-copy")
	end)
	bee.addClick(self.SearchButton, function()
		self:SearchFriend()
		bee.logEvent("friends-main-search")
	end)

	bee.addValueChanged(self.InputFieldSearch, function()
		local searchText = bee.getText(self.InputFieldSearch, "InputField")
		if searchText ~= "" then
			self.SearchButton:SetActive(false)
			self.ClearButton:SetActive(true)
			self:SearchFriend()
		else
			self.SearchButton:SetActive(true)
			self.ClearButton:SetActive(false)

			self:onClickClearButton()
		end
	end, "InputField")
end

function P:onStart()
	self:initFriendList()
	self:initSearchFriendList()
	self:initRecentList()

	bee.setText(self.SelfIDText, _T("LAB_FRIENDS_2") .. PlayerModel:getUid())

	local startIndex = TabIndex.FriendsList
	if self._params and self._params.jump and self._params.jump.sub_page then
		startIndex = self._params.jump.sub_page[1]
	end
	bee.setCheck(self.tabToggleList[startIndex])
	self:onClickTabToggle(startIndex)
	
    FriendModel:initFriendList()
end

function P:onClickTabToggle(index)
	if index == self._selectedIndex then
		return
	end
	self._selectedIndex = index
	self:playToggleInto(self.tabToggleList[self._selectedIndex])

	self.friendList:clear()
	bee.setText(self.InputFieldSearch, "", "InputField")

	if index == TabIndex.FriendsList then
		FriendModel:requestFriendList()
	elseif index == TabIndex.FindFriends then
		self._searchFriendDatas = {}
		self:setSearchFriend(_T("LAB_FRIENDS_12"))
		FriendModel:requestRecentGameList(function()
			self:setRecentList()
		end)
	elseif index == TabIndex.ApplyList then
		self:setFriendList(FriendModel:getApplyFriendList(), _T("LAB_FRIENDS_37"))
	elseif index == TabIndex.BlockedList then
		self:setFriendList(FriendModel:getBlockedList(), _T("LAB_FRIENDS_39"))
	end
end

function P:onClickClearButton()
	if self._searchTag then
		scheduler:removeTag(self._searchTag)
		self._searchTag = nil
	end

	bee.setText(self.InputFieldSearch, "", "InputField")

	if self._selectedIndex == TabIndex.FriendsList then
		self:setFriendList(FriendModel:getFriendList(), _T("LAB_FRIENDS_43"))
	elseif self._selectedIndex == TabIndex.FindFriends then
		self:setSearchFriend(_T("LAB_FRIENDS_12"))
	elseif self._selectedIndex == TabIndex.ApplyList then
		self:setFriendList(FriendModel:getApplyFriendList(), _T("LAB_FRIENDS_37"))
	elseif self._selectedIndex == TabIndex.BlockedList then
		self:setFriendList(FriendModel:getBlockedList(), _T("LAB_FRIENDS_39"))
	end
end

function P:setFriendList(datas, blankTxt)
	self.HalfList:SetActive(false)
	self.Bottom:SetActive(false)

	bee.setText(self.FriendsCountText, _T("LAB_FRIENDS_3") .. FriendModel:getFriendCount() .. "/" .. VipModel:getFriendLimit())

	if #datas > 0 then
		self.FullList:SetActive(true)
		self.Blank:SetActive(false)
		self.friendList:setDatas(datas)
	else
		self.FullList:SetActive(false)
		self.Blank:SetActive(true)
		self.friendList:clear()

		bee.setText(self.BlankTips, blankTxt)
		self.GoButton:SetActive(self._selectedIndex == TabIndex.FriendsList)
	end

	if self._selectedIndex == TabIndex.ApplyList then
		FriendModel:refreshApplyRedPoint()
	end
end

function P:setSearchFriend(blankTxt)
	self.HalfList:SetActive(true)
	self.Bottom:SetActive(true)
	self.FullList:SetActive(false)

	if self._searchFriendDatas and #self._searchFriendDatas > 0 then
		self.Blank:SetActive(false)
		self.searchFriendList:setDatas(self._searchFriendDatas)
	else
		self.Blank:SetActive(true)
		self.searchFriendList:clear()

		bee.setText(self.BlankTips, blankTxt)
		self.GoButton:SetActive(false)
	end
end

function P:setRecentList()
	local datas = FriendModel:getRecentGameList()

	if #datas <= 0 then
		self.RecentBlankTips:SetActive(true)
	else
		self.RecentBlankTips:SetActive(false)
		self.ListRecent:setDatas(datas)
	end
end

function P:initFriendList()
	self.friendList = UiListEx:create(self.FullList)
	self.friendList:setWidth(210)
	self.friendList:setCreateFunc(function(data)
		return CU.GameObject.Instantiate(self.ItemPlayer)
	end)
	self.friendList:setRefreshFunc(function(data, item)
		self:setFriendItem(item, data)
	end)
end

function P:initSearchFriendList()
	self.searchFriendList = UiListEx:create(self.HalfList)
	self.searchFriendList:setWidth(210)
	self.searchFriendList:setCreateFunc(function(data)
		return CU.GameObject.Instantiate(self.ItemPlayer)
	end)
	self.searchFriendList:setRefreshFunc(function(data, item)
		self:setFriendItem(item, data)
	end)
end

function P:initRecentList()
	self.ListRecent = UiListEx:create(self.RecentList)
	self.ListRecent:setWidth(600)
	self.ListRecent:setCreateFunc(function(data)
		return CU.GameObject.Instantiate(self.ItemRecentPlayer)
	end)
	self.ListRecent:setRefreshFunc(function(data, item)
		self:setRecentItem(item, data)
	end)
end

function P:setFriendItem(item, data)
	local NameText = self:find("NameText", item)
	local EditButton = self:find("EditButton", item)
	local Avatar = self:find("Avatar", item)
	local AvatarIcon = self:find("Avatar/Mask/ImageIcon", item)
	local AvatarFrame = self:find("Avatar/AvatarFrame", item)
	local RankIcon = self:find("Rank/RankIcon", item)
	local RankText = self:find("Rank/RankText", item)
	local TitleIcon = self:find("TitleIcon", item)

	local FriendCont = self:find("FriendCont", item)
	local SearchCont = self:find("SearchCont", item)
	local ApplyCont = self:find("ApplyCont", item)
	local BlockedCont = self:find("BlockedCont", item)
	
	local Online = self:find("Online", FriendCont)
	local OfflineText = self:find("OfflineText", FriendCont)
	local BlockButton = self:find("BlockButton", FriendCont)
	local DeleteButton = self:find("DeleteButton", FriendCont)

	local AppliedText = self:find("AppliedText", SearchCont)
	local AddButton = self:find("AddButton", SearchCont)

	local ApplyTimeText = self:find("ApplyTimeText", ApplyCont)
	local ListAcceptButton = self:find("ListAcceptButton", ApplyCont)
	local ListRejectButton = self:find("ListRejectButton", ApplyCont)
	local ListBlockButton = self:find("ListBlockButton", ApplyCont)

	local RevertButton = self:find("RevertButton", BlockedCont)

	if self._selectedIndex == TabIndex.FriendsList or self._selectedIndex == TabIndex.BlockedList then
		EditButton:SetActive(true)
	else
		EditButton:SetActive(false)
	end

	bee.setText(RankText, data.level)
	bee.setIconInAtlas(RankIcon, tpl_level[data.level].icon)

	if data.mark and data.mark ~= "" then
		bee.setText(NameText, data.mark)
	else
		bee.setText(NameText, data.nickname)
	end
	bee.setIcon(AvatarIcon, PlayerModel:getAvatarIcon(data.avatar))
	GF.setFrameImage(AvatarFrame, data.using_frame)
	GF.setTitleImage(TitleIcon, data.using_title)

	if self._selectedIndex == TabIndex.FriendsList then
		FriendCont:SetActive(true)
		SearchCont:SetActive(false)
		ApplyCont:SetActive(false)
		BlockedCont:SetActive(false)

		Online:SetActive(data.is_online)
		OfflineText:SetActive(not data.is_online)
		if not data.is_online then
			bee.setText(OfflineText, FriendModel:getOfflineTimeText(data.last_login_time))
		end

		bee.removeAllClick(BlockButton)
		bee.addClick(BlockButton, function()
			Game:playSound("ui_button_confirm")
			self:onClickBlock(data, function()
				bee.logEvent("friends-main-blacklist", data.uid)
			end)
		end)
		bee.removeAllClick(DeleteButton)
		bee.addClick(DeleteButton, function()
			Game:playSound("ui_button_confirm")
			self:onClickDeleteFriend(data)
		end)
	elseif self._selectedIndex == TabIndex.FindFriends then
		FriendCont:SetActive(false)
		SearchCont:SetActive(true)
		ApplyCont:SetActive(false)
		BlockedCont:SetActive(false)

		if data.uid == PlayerModel:getUid() then
			AppliedText:SetActive(false)
			AddButton:SetActive(false)
		elseif data.status == FRIEND_STATUS.NORMAL then
			AppliedText:SetActive(false)
			AddButton:SetActive(false)
		elseif data.status == FRIEND_STATUS.SEND_APPLY then
			AppliedText:SetActive(true)
			AddButton:SetActive(false)
		else
			AppliedText:SetActive(false)
			AddButton:SetActive(true)
		end

		bee.removeAllClick(AddButton)
		bee.addClick(AddButton, function()
			Game:playSound("ui_button_confirm")
			FriendModel:addFriend(data.uid, function(friend_uid)
				if friend_uid == data.uid then
					data.status = FRIEND_STATUS.NORMAL
					AppliedText:SetActive(false)
					AddButton:SetActive(false)
				else
					data.status = FRIEND_STATUS.SEND_APPLY
					AppliedText:SetActive(true)
					AddButton:SetActive(false)
				end
			end)
			bee.logEvent("friends-search-add", data.uid)
		end)
	elseif self._selectedIndex == TabIndex.ApplyList then
		FriendCont:SetActive(false)
		SearchCont:SetActive(false)
		ApplyCont:SetActive(true)
		BlockedCont:SetActive(false)

		bee.setText(ApplyTimeText, _T("LAB_FRIENDS_44") .. FriendModel:getOfflineTimeText(data.time))

		bee.removeAllClick(ListAcceptButton)
		bee.addClick(ListAcceptButton, function()
			Game:playSound("ui_button_confirm")
			FriendModel:addFriend(data.uid, function()
				UiManager:showToast(_T("LAB_FRIENDS_34"))
			end)
			bee.logEvent("friends-requests-accept", data.uid)
		end)
		bee.removeAllClick(ListBlockButton)
		bee.addClick(ListBlockButton, function()
			Game:playSound("ui_button_confirm")
			self:onClickBlock(data, function()
				bee.logEvent("friends-requests-blacklist", data.uid)
			end)
		end)
		bee.removeAllClick(ListRejectButton)
		bee.addClick(ListRejectButton, function()
			Game:playSound("ui_button_confirm")
			FriendModel:deleteApply(data.uid)
			bee.logEvent("friends-requests-remove", data.uid)
		end)
	elseif self._selectedIndex == TabIndex.BlockedList then
		FriendCont:SetActive(false)
		SearchCont:SetActive(false)
		ApplyCont:SetActive(false)
		BlockedCont:SetActive(true)

		bee.removeAllClick(RevertButton)
		bee.addClick(RevertButton, function()
			Game:playSound("ui_button_confirm")
			FriendModel:unblockFriend(data.uid)
			bee.logEvent("friends-blacklist-remove", data.uid)
		end)
	end

	bee.removeAllClick(EditButton)
	bee.addClick(EditButton, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("FriendRemark", {data = data})
		if self._selectedIndex == TabIndex.BlockedList then
			bee.logEvent("friends-blacklist-setAlias", data.uid)
		else
			bee.logEvent("friends-main-setAlias", data.uid)
		end
	end)

	bee.removeAllClick(Avatar)
	bee.addClick(Avatar, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("InformationMainNew", {uid = data.uid})
	end)
end

function P:setRecentItem(item, data)
	local Avatar = self:find("Avatar", item)
	local AvatarIcon = self:find("Avatar/Mask/ImageIcon", item)
	local AvatarFrame = self:find("Avatar/AvatarFrame", item)
	local RankIcon = self:find("Rank/RankIcon", item)
	local RankText = self:find("Rank/RankText", item)
	local TitleIcon = self:find("TitleIcon", item)
	local NameText = self:find("NameText", item)
	local AddButton = self:find("AddButton", item)
	local AppliedText = self:find("AppliedText", item)

	if data.mark and data.mark ~= "" then
		bee.setText(NameText, data.mark)
	else
		bee.setText(NameText, data.nickname)
	end
	bee.setIcon(AvatarIcon, PlayerModel:getAvatarIcon(data.avatar))
	GF.setFrameImage(AvatarFrame, data.using_frame)
	GF.setTitleImage(TitleIcon, data.using_title)
	bee.setText(RankText, data.level)
	bee.setIconInAtlas(RankIcon, tpl_level[data.level].icon)
	if data.status == FRIEND_STATUS.NORMAL then
		AppliedText:SetActive(false)
		AddButton:SetActive(false)
	elseif data.status == FRIEND_STATUS.SEND_APPLY then
		AppliedText:SetActive(true)
		AddButton:SetActive(false)
	else
		AppliedText:SetActive(false)
		AddButton:SetActive(true)
	end

	bee.removeAllClick(AddButton)
	bee.addClick(AddButton, function()
		Game:playSound("ui_button_confirm")
		FriendModel:addFriend(data.uid, function(friend_uid)
			if friend_uid == data.uid then
				data.status = FRIEND_STATUS.NORMAL
				AppliedText:SetActive(false)
				AddButton:SetActive(false)
			else
				data.status = FRIEND_STATUS.SEND_APPLY
				AppliedText:SetActive(true)
				AddButton:SetActive(false)
			end
		end)
		bee.logEvent("friends-search-recommend", data.uid)
	end)
	bee.removeAllClick(Avatar)
	bee.addClick(Avatar, function()
		Game:playSound("ui_button_confirm")
		UiManager:showUI("InformationMainNew", {uid = data.uid})
	end)
end

function P:SearchFriend()
	local searchText = bee.getText(self.InputFieldSearch, "InputField")
	if searchText == "" then
		UiManager:showToast(_T("LAB_FRIENDS_12"))
		return
	end

	if self._searchTag then
		scheduler:removeTag(self._searchTag)
		self._searchTag = nil
	end

	self._searchTag = self:once(0.8, function()
		if self._selectedIndex == TabIndex.FriendsList then
			local datas = FriendModel:searchLocalFriendList(FriendModel:getFriendList(), searchText)
			self:setFriendList(datas, _T("LAB_FRIENDS_30"))
		elseif self._selectedIndex == TabIndex.FindFriends then
			FriendModel:searchFriend(searchText, function(data)
				self._searchFriendDatas = data
				self:setSearchFriend(_T("LAB_FRIENDS_30"))
			end)
		elseif self._selectedIndex == TabIndex.ApplyList then
			local datas = FriendModel:searchLocalFriendList(FriendModel:getApplyFriendList(), searchText)
			self:setFriendList(datas, _T("LAB_FRIENDS_30"))
		elseif self._selectedIndex == TabIndex.BlockedList then
			local datas = FriendModel:searchLocalFriendList(FriendModel:getBlockedList(), searchText)
			self:setFriendList(datas, _T("LAB_FRIENDS_30"))
		end
	end)
end

function P:onClickBlock(data, cb)
	local name
	if data.mark and data.mark ~= "" then
		name = data.mark
	else
		name = data.nickname
	end
    UiManager:showTip({
        text = _F("LAB_FRIENDS_26", name),
        onSure = function()
            FriendModel:blockFriend(data.uid)
			if cb then cb() end
        end
    })
end

function P:onClickDeleteFriend(data)
	local name
	if data.mark and data.mark ~= "" then
		name = data.mark
	else
		name = data.nickname
	end
    UiManager:showTip({
        text = _F("LAB_FRIENDS_23", name),
        onSure = function()
            FriendModel:deleteFriend(data.uid)
			bee.logEvent("friends-main-remove", data.uid)
        end
    })
end

function P:refreshList()
	if self._selectedIndex == TabIndex.FriendsList then
		self:setFriendList(FriendModel:getFriendList(), _T("LAB_FRIENDS_43"))
	elseif self._selectedIndex == TabIndex.FindFriends then
		self:setSearchFriend(_T("LAB_FRIENDS_12"))
	elseif self._selectedIndex == TabIndex.ApplyList then
		self:setFriendList(FriendModel:getApplyFriendList(), _T("LAB_FRIENDS_37"))
	elseif self._selectedIndex == TabIndex.BlockedList then
		self:setFriendList(FriendModel:getBlockedList(), _T("LAB_FRIENDS_39"))
	end
end

function P:evt_friendList(refreshType)
	if self._selectedIndex == TabIndex.FindFriends then
		return
	end

	if refreshType == FRIEND_LIST_TYPE.FRIENDS and self._selectedIndex ~= TabIndex.FriendsList then
		return
	elseif refreshType == FRIEND_LIST_TYPE.APPLY and self._selectedIndex ~= TabIndex.ApplyList then
		return
	elseif refreshType == FRIEND_LIST_TYPE.BLOCKED and self._selectedIndex ~= TabIndex.BlockedList then
		return
	end

	self:refreshList()
end

return P