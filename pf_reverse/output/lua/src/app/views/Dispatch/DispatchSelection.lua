local P = class("DispatchSelection", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Panel = self:find("Center/Panel", AnimRoot)

	local Title = self:find("Title", Panel)
	self.CampNameText = self:find("CampNameText", Title)
	self.CampLevel = self:find("CampLevel", Title)
	self.CampIcon = self:find("CampIcon", Title)

	self.Character = self:find("Character", Panel)
	self.Empty = self:find("Empty", self.Character)
	self.CharacterListObj = self:find("CharacterList", self.Character)
	self.CharacterItem = self:find("CharacterItem", self.CharacterListObj)
	self.CharacterItem:SetActive(false)
	local TabFilter = self:find("TabFilter", self.Character)
	self.FilterButtonBg = self:find("FilterButtonBg", TabFilter)
	self.FilterButton = self:find("FilterButton", self.FilterButtonBg)
	self.FilterArrowDown = self:find("FilterArrowDown", self.FilterButton)
	self.FilterArrowUp = self:find("FilterArrowUp", self.FilterButton)
	self.FilterArrowDown:SetActive(false)
	self.FilterArrowUp:SetActive(true)
	self.CurTabText = self:find("CurTabText", self.FilterButtonBg)
	self.FilterCont = self:find("FilterCont", TabFilter)
	self.FilterCont:SetActive(false)
	self.FilterItem = self:find("FilterItem", self.FilterCont)
	self.CloseFilterMask = self:find("CloseFilterMask", TabFilter)
	self.CloseFilterMask:SetActive(false)

	local Detail = self:find("Detail", Panel)
	self.DetailTitleBg = self:find("DetailTitleBg", Detail)
	self.EventNameText = self:find("EventNameText", Detail)
	self._selectedRoleItemList = {}
	for i = 1, 2 do
		self._selectedRoleItemList[i] = self:find("DetailsCandidates/SelectedRole" .. i, Detail)
	end
	self.AwardListCont = self:find("DetailsMain/Award/AwardList/Viewport/Content", Detail)
    self.ExpAwardItem = self:find("ExpAwardItem", self.AwardListCont)
    self.BondAwardItem = self:find("BondAwardItem", self.AwardListCont)
    self.RoleStarAwardItem = self:find("RoleStarAwardItem", self.AwardListCont)
    self.DispatchExpAwardItem = self:find("DispatchExpAwardItem", self.AwardListCont)
    self.RewardBonusAwardItem = self:find("RewardBonusAwardItem", self.AwardListCont)
    self.DetailTimeText = self:find("DetailsMain/Time/DetailTimeText", Detail)
    self.ReselectButton = self:find("DetailsMain/ReselectButton", Detail)

    self.DispatchButton = self:find("DispatchButton", Panel)

	self.CloseButton = self:find("CloseButton", Panel)
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)

	bee.addClick(self.CloseFilterMask, function()
		self.FilterArrowDown:SetActive(false)
		self.FilterArrowUp:SetActive(true)
		self.CloseFilterMask:SetActive(false)
		self.FilterCont:SetActive(false)
	end)
	bee.addClick(self.FilterButtonBg, function()
		Game:playSound("ui_button_confirm")
		self.FilterArrowDown:SetActive(true)
		self.FilterArrowUp:SetActive(false)
		self.CloseFilterMask:SetActive(true)
		self.FilterCont:SetActive(true)
	end)
	bee.addClick(self.FilterButton, function()
		Game:playSound("ui_button_confirm")
		self.FilterArrowDown:SetActive(true)
		self.FilterArrowUp:SetActive(false)
		self.CloseFilterMask:SetActive(true)
		self.FilterCont:SetActive(true)
	end)

	bee.addClick(self.ReselectButton, function()
		Game:playSound("ui_button_confirm")
		self.selectedRoleList[self._selectedIndex] = nil
		self:setDetailCont()
		self:refreshRoleSelected()
	end)

	bee.addClick(self.DispatchButton, function()
		Game:playSound("ui_button_confirm")
		self:onClickDispatchButton()
	end)

	self.BottomText = self:find("BottomText", Panel)

	self.filterItemList = {}
	self.selectedRoleList = {}
end

function P:onStart()
	self._eventId = self._params.event
	self._eventCfg = tpl_event_info[self._eventId]
	if not self._eventCfg then
		return
	end

	self._eventData = DispatchModel:getEvent(self._eventId)
	self._campCfg = tpl_camp_detail[self._eventCfg.campInt]
	self._campLevel = DispatchModel:getCampLevel(self._eventCfg.campInt)
	self._maxRoleCount = tpl_camp_info[self._campLevel].members_limit

	self._selectFilterId = -1
	self._selectedIndex = 1

	self:setEventCont()
	self:initCharacterList()
	self:setCharacterList()
	self:initFilter()
	self:refreshFilterCont()
	self:setSelectedDetail()
	self:setDetailCont()

	if self._params.item_id == GPropId.OrdinaryDispatch then
		local totalTimes = tpl_constdata.Dispatch_Ordinary_Num
		local remainTimes = DispatchModel:getRemainOrdinaryTimes()
		bee.setText(self.BottomText, _F("LAB_DISPATCH_23", remainTimes, totalTimes))
	else
		bee.setText(self.BottomText, _F("LAB_DISPATCH_132", tpl_constdata.Dispatch_Advanced_Num))
	end
end

function P:setEventCont()
	bee.setText(self.CampNameText, _F("LAB_DISPATCH_02", _T(self._campCfg.camp_name)))
	bee.setIconInAtlas(self.CampIcon, self._campCfg.camp_icon)
	bee.setIcon(self.CampLevel, "dispatch_main_tap_camp_bg_" .. self._campLevel, "Dispatch")
	bee.setText(self.EventNameText, _T(self._eventCfg.event_name))
	bee.setIcon(self.DetailTitleBg, "dispatch_main_details_title_bg_0" .. self._eventCfg.event_level, "Dispatch")

	for i = 1, 2 do
		self._selectedRoleItemList[i]:SetActive(i <= self._maxRoleCount)
	end
end

function P:initCharacterList()
    self.charactetList = UiListEx:create(self.CharacterListObj)
    self.charactetList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.CharacterItem)
    end)
    self.charactetList:setRefreshFunc(function(data, item)
        self:setCharacterItem(item, data)
    end)
    self.charactetList:setWidth(194)
end

function P:setCharacterList()
	local eventCfg = tpl_event_info[self._eventId]
    local list = {}
    for k, v in pairs(CharacterModel:getOwnedCharacters()) do
    	local dispatchData = DispatchModel:getDispatchRoleData(v.role_id)
    	local remainTimes = dispatchData.remain_dispatch_times
    	if self._params.item_id == GPropId.SeniorDispatch then
    		remainTimes = dispatchData.remain_advanced_dispatch_times
    	end
    	if remainTimes > 0 and not DispatchModel:getRoleDispatchingEvent(v.role_id) and dispatchData.role_star >= eventCfg.character_level then
	        if self._selectFilterId ~= -1 then
	        	if v.info.campInt == self._selectFilterId then
	        		table.insert(list, {role = v, dispatchData = DispatchModel:getDispatchRoleData(v.role_id)})
	        	end
	        else
	            table.insert(list, {role = v, dispatchData = DispatchModel:getDispatchRoleData(v.role_id)})
	        end
	    end
    end
    table.sort(list, function(a, b)
    	local sumA = 1000
    	local sumB = 1000

    	if a.role.info.campInt == eventCfg.campInt then
    		sumA = sumA + 100
    	end
    	if b.role.info.campInt == eventCfg.campInt then
    		sumB = sumB + 100
    	end

    	if a.dispatchData.role_star > b.dispatchData.role_star then
    		sumA = sumA + 10
    	end
    	if b.dispatchData.role_star > a.dispatchData.role_star then
    		sumB = sumB + 10
    	end

    	if a.role.role_id < b.role.role_id then
    		sumA = sumA + 1
    	end
    	if b.role.role_id < a.role.role_id then
    		sumB = sumB + 1
    	end

    	return sumA > sumB
	end)

    if next(list) then
    	self.CharacterListObj:SetActive(true)
    	self.Empty:SetActive(false)
		self.charactetList:setDatas(list)
	else
		self.CharacterListObj:SetActive(false)
		self.Empty:SetActive(true)
	end
end

function P:setCharacterItem(item, data)
	local Information = self:find("Information", item)
	local CampIcon = self:find("CampIcon", Information)
	local RoleNameText = self:find("RoleNameText", Information)
	local Stars = self:find("Stars", Information)
	local RewardBonus = self:find("Buff/RewardBonus", Information)
	local BaseRewardUp = self:find("Buff/BaseRewardUp", Information)
	local TimeReduce = self:find("Buff/TimeReduce", Information)
	local Decelerate = self:find("Buff/Decelerate", Information)
	local State = self:find("State", item)
	local Break = self:find("Break", State)
	local Dispatching = self:find("Dispatching", State)
	local TimeText = self:find("TimeText", Dispatching)
	local Leisure = self:find("Leisure", State)
	local NumText = self:find("NumText", State)
	local AvatarIcon = self:find("Avatar/avatar_frame_01_mask/AvatarIcon", item)
	local Selected = self:find("Selected", item)

	local role = data.role
	local dispatchData = data.dispatchData

	local skinCfg = role:getSkinData()
	bee.setIconInAtlas(AvatarIcon, tpl_props[skinCfg.avatar].icon)
	bee.setIcon(CampIcon, "dispatch_main_camp_" .. role.info.campInt, "Dispatch", true)
	bee.setText(RoleNameText, role:getName())

	for i = 1, 5 do
		self:find("Star" .. i, Stars):SetActive(i <= dispatchData.role_star)
	end

	local levelCfg = tpl_character_info[dispatchData.role_star]
	local campInfoCfg = tpl_camp_info[self._campLevel]

	-- 派遣时间
	local timeBuff = levelCfg.time_reduce
	if role.info.campInt ~= self._eventCfg.campInt then
		timeBuff = timeBuff - tpl_constdata.Dispatch_Camp_Debuff
	end
	if timeBuff > 0 then
		TimeReduce:SetActive(true)
		Decelerate:SetActive(false)
		bee.setText(self:find("NumText", TimeReduce), timeBuff / 100 .. "%")
	elseif timeBuff < 0 then
		TimeReduce:SetActive(false)
		Decelerate:SetActive(true)
		bee.setText(self:find("NumText", Decelerate), timeBuff / 100 .. "%")
	else
		TimeReduce:SetActive(false)
		Decelerate:SetActive(false)
	end

	-- 基础奖励提升
	local baseBuff = levelCfg.base_reward_up
	if baseBuff > 0 then
		BaseRewardUp:SetActive(true)
		bee.setText(self:find("NumText", BaseRewardUp), baseBuff / 100 .. "%")
	else
		BaseRewardUp:SetActive(false)
	end

	-- 彩蛋概率加成
	local bonusRewardBuff = 0
	if role.info.campInt == self._eventCfg.campInt then
		bonusRewardBuff = levelCfg.reward_bonus
	end
	if bonusRewardBuff > 0 then
		RewardBonus:SetActive(true)
		bee.setText(self:find("NumText", RewardBonus), bonusRewardBuff / 100 .. "%")
	else
		RewardBonus:SetActive(false)
	end

	Selected:SetActive(self:_isInSelected(role.role_id))

	bee.removeAllClick(item)
	bee.addClick(item, function()
		Game:playSound("ui_button_confirm")
		local index = self:_isInSelected(role.role_id)
		if index then
			-- 取消选择
			self.selectedRoleList[index] = nil
		else
			if self:_getCurSelectedCount() < self._maxRoleCount then
				-- 加派牌手
				for i = 1, self._maxRoleCount do
					if not self.selectedRoleList[i] then
						self.selectedRoleList[i] = role.role_id
						self._selectedIndex = i
						break
					end
				end
			else
				-- 替换当前牌手
				self.selectedRoleList[self._selectedIndex] = role.role_id
			end
		end
		self:setDetailCont()
		self:refreshRoleSelected()
	end)
end

-- 当前已选人数
function P:_getCurSelectedCount()
	local count = 0
	for k, v in pairs(self.selectedRoleList) do
		if v then
			count = count + 1
		end
	end
	return count
end

function P:_isInSelected(role_id)
	for k, v in pairs(self.selectedRoleList) do
		if v == role_id then
			return k
		end
	end
	return false
end

function P:refreshRoleSelected()
	for k, v in pairs(self.charactetList:getShows()) do
		local Selected = self:find("Selected", self.charactetList:getNode(v))
		Selected:SetActive(self:_isInSelected(self.charactetList:getData(v).role.role_id))
	end
end

function P:initFilter()
    local datas = {}
    for k, v in pairs(tpl_camp_detail) do
        table.insert(datas, v)
    end
    table.sort(datas, function(a, b) return a.campInt < b.campInt end)

    self.filterItemList[-1] = self.FilterItem

	for i, v in ipairs(datas) do
		local copyItem = CU.GameObject.Instantiate(self.FilterItem)
		copyItem.transform:SetParent(self.FilterCont.transform)
		copyItem.transform.localPosition = bee.v3(0, 0, 0)
		copyItem.transform.localScale = bee.v3(1, 1, 1)
		copyItem:SetActive(true)

		self.filterItemList[v.campInt] = copyItem

		bee.setText(self:find("Item/On/Text", copyItem), _F("LAB_DISPATCH_02", _T(v.camp_name)))
		bee.setText(self:find("Item/Off/Text", copyItem), _F("LAB_DISPATCH_02", _T(v.camp_name)))

		bee.removeAllClick(self:find("Item", copyItem))
		bee.addClick(self:find("Item", copyItem), function()
			Game:playSound("ui_button_confirm")
			if self._selectFilterId == v.campInt then
				return
			end
			self._selectFilterId = v.campInt
			self:setCharacterList()
			self:refreshFilterCont()

			self.FilterArrowDown:SetActive(false)
			self.FilterArrowUp:SetActive(true)
			self.CloseFilterMask:SetActive(false)
			self.FilterCont:SetActive(false)
		end)
	end

	bee.setText(self:find("Item/On/Text", self.FilterItem), _T("TAB_SHOP_THEME_3"))
	bee.setText(self:find("Item/Off/Text", self.FilterItem), _T("TAB_SHOP_THEME_3"))
	bee.removeAllClick(self:find("Item", self.FilterItem))
	bee.addClick(self:find("Item", self.FilterItem), function()
		Game:playSound("ui_button_confirm")
		if self._selectFilterId == -1 then
			return
		end
		self._selectFilterId = -1
		self:setCharacterList()
		self:refreshFilterCont()

		self.FilterArrowDown:SetActive(false)
		self.FilterArrowUp:SetActive(true)
		self.CloseFilterMask:SetActive(false)
		self.FilterCont:SetActive(false)
	end)

	self:refreshFilterCont()
end

function P:refreshFilterCont()
	for k, v in pairs(self.filterItemList) do
		self:find("Item/On", v):SetActive(self._selectFilterId == k)
		self:find("Item/Off", v):SetActive(self._selectFilterId ~= k)
	end
	if self._selectFilterId == -1 then
		bee.setText(self.CurTabText, _T("TAB_SHOP_THEME_3"))
	else
		bee.setText(self.CurTabText, _F("LAB_DISPATCH_02", _T(tpl_camp_detail[self._selectFilterId].camp_name)))
	end
end

function P:setDetailCont()
	for i = 1, self._maxRoleCount do
		self:setSelectedRoleItem(self._selectedRoleItemList[i], self.selectedRoleList[i], i)
	end
	self:setSelectedDetail()
end

function P:setSelectedRoleItem(selectedItem, roleId, index)
	local Item = self:find("Item", selectedItem)
	local Avatar = self:find("Avatar", Item)
	local TabOn = self:find("TabOn", Avatar)
	local TabOff = self:find("TabOff", Avatar)
	local AvatarIcon = self:find("avatar_frame_01_mask/AvatarIcon", Avatar)
	local AddonButton = self:find("AddonButton", Item)
	local Selected = self:find("Selected", selectedItem)
	
	Selected:SetActive(self._selectedIndex == index)
	TabOn:SetActive(self._selectedIndex == index)
	TabOff:SetActive(self._selectedIndex ~= index)

	if roleId then
		Avatar:SetActive(true)
		local skinCfg = CharacterModel:getRole(roleId):getSkinData()
		bee.setIconInAtlas(AvatarIcon, tpl_props[skinCfg.avatar].icon, true)
	else
		Avatar:SetActive(false)
	end

	bee.removeAllClick(Item)
	bee.addClick(Item, function()
		Game:playSound("ui_button_confirm")
		self._selectedIndex = index
		self:setSelectedDetail()

		for i = 1, self._maxRoleCount do
			self:find("Selected", self._selectedRoleItemList[i]):SetActive(self._selectedIndex == i)
			self:find("Item/Avatar/TabOn", self._selectedRoleItemList[i]):SetActive(self._selectedIndex == i)
			self:find("Item/Avatar/TabOff", self._selectedRoleItemList[i]):SetActive(self._selectedIndex ~= i)
		end
	end)
end

function P:setSelectedDetail()
	local role_id = self.selectedRoleList[self._selectedIndex]
	local roleInfoCfg
	if role_id then
		local roleData = DispatchModel:getDispatchRoleData(role_id)
		roleInfoCfg = tpl_character_info[roleData.role_star]
	end
	local campInfoCfg = tpl_camp_info[self._campLevel]

    local add = campInfoCfg.base_reward_up or 0
    if roleInfoCfg then
    	add = add + roleInfoCfg.base_reward_up
    end

	-- 玩家等级经验
    if self._eventCfg.reward_exp > 0 and DispatchModel:isCanRewardExp() then
        self.ExpAwardItem:SetActive(true)
        local num = math.floor(self._eventCfg.reward_exp * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.ExpAwardItem), {item_id = GPropId.ExpDispatch, num = num}):bindTips()
        if add > 0 then
        	self:find("BaseRewardUp", self.ExpAwardItem):SetActive(true)
        	bee.setText(self:find("BaseRewardUp/BaseRewardUpText", self.ExpAwardItem), add / 100 .. "%")
        else
        	self:find("BaseRewardUp", self.ExpAwardItem):SetActive(false)
        end
    else
        self.ExpAwardItem:SetActive(false)
    end

    -- 派遣角色好感度
    if self._eventCfg.reward_affinity > 0 and DispatchModel:isCanRewardBond() then
        self.BondAwardItem:SetActive(true)
        local num = math.floor(self._eventCfg.reward_affinity * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.BondAwardItem), {item_id = GPropId.BondDispatch, num = num}):bindTips()
        if add > 0 then
        	self:find("BaseRewardUp", self.BondAwardItem):SetActive(true)
        	bee.setText(self:find("BaseRewardUp/BaseRewardUpText", self.BondAwardItem), add / 100 .. "%")
        else
        	self:find("BaseRewardUp", self.BondAwardItem):SetActive(false)
        end
    else
        self.BondAwardItem:SetActive(false)
    end

    -- 角色星级经验
    if self._eventCfg.reward_star_exp > 0 then
        self.RoleStarAwardItem:SetActive(true)
        local num = math.floor(self._eventCfg.reward_star_exp * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.RoleStarAwardItem), {item_id = GPropId.RoleDispatchExp, num = num}):bindTips()
        if add > 0 then
        	self:find("BaseRewardUp", self.RoleStarAwardItem):SetActive(true)
        	bee.setText(self:find("BaseRewardUp/BaseRewardUpText", self.RoleStarAwardItem), add / 100 .. "%")
        else
        	self:find("BaseRewardUp", self.RoleStarAwardItem):SetActive(false)
        end
    else
        self.RoleStarAwardItem:SetActive(false)
    end

    -- 事务所品质提升/解锁道具
    if self._eventCfg.reward_campquality > 0 then
        self.DispatchExpAwardItem:SetActive(true)
        local num = math.floor(self._eventCfg.reward_campquality * (1 + add / 10000))
        PropItem:create(self:find("PropItem", self.DispatchExpAwardItem), {item_id = GPropId.CampDispatchUpgrade, num = num}):bindTips()
        if add > 0 then
        	self:find("BaseRewardUp", self.DispatchExpAwardItem):SetActive(true)
        	bee.setText(self:find("BaseRewardUp/BaseRewardUpText", self.DispatchExpAwardItem), add / 100 .. "%")
        else
        	self:find("BaseRewardUp", self.DispatchExpAwardItem):SetActive(false)
        end
    else
        self.DispatchExpAwardItem:SetActive(false)
    end

    -- 彩蛋奖励
    if role_id and self._eventCfg.reward_bonus_item then
    	local isBonus = tpl_character[role_id].campInt == self._eventCfg.campInt
        if isBonus then
	        self.RewardBonusAwardItem:SetActive(true)
	        PropItem:create(self:find("PropItem", self.RewardBonusAwardItem), {item_id = GPropId.DispatchBonus, num = 0})
	        
	        local bonusAdd = self._eventCfg.reward_bonus or 0
	        if roleInfoCfg then
	        	bonusAdd = bonusAdd + roleInfoCfg.reward_bonus
	        end
	        if bonusAdd > 0 then
	        	self:find("Buff", self.RewardBonusAwardItem):SetActive(true)
	        	bee.setText(self:find("Buff/NumText", self.RewardBonusAwardItem), bonusAdd / 100 .. "%")
	        else
	        	self:find("Buff", self.RewardBonusAwardItem):SetActive(false)
	        end

	        bee.removeAllClick(self:find("PropItem", self.RewardBonusAwardItem))
	        bee.addClick(self:find("PropItem", self.RewardBonusAwardItem), function()
	            local rewardsBonus = {}
	            for i = 1, #self._eventCfg.reward_bonus_item, 3 do
	                table.insert(rewardsBonus, {item_id = self._eventCfg.reward_bonus_item[i], num = self._eventCfg.reward_bonus_item[i + 1], weight = self._eventCfg.reward_bonus_item[i + 2]})
	            end
	            UiManager:showUI("DispatchRewardBondTip", {items = rewardsBonus, target = self.RewardBonusAwardItem})
	        end)
	    else
	    	self.RewardBonusAwardItem:SetActive(false)
	    end
    else
        self.RewardBonusAwardItem:SetActive(false)
    end

    -- 派遣时间
    local timeBuff = campInfoCfg.time_reduce or 0
    if roleInfoCfg then
    	timeBuff = timeBuff + roleInfoCfg.time_reduce
    	if CharacterModel:getRole(role_id).info.campInt ~= self._eventCfg.campInt then
    		timeBuff = timeBuff - tpl_constdata.Dispatch_Camp_Debuff
    	end
    end
    local dt = math.ceil(self._eventCfg.base_time * (1 - timeBuff / 10000))
    if timeBuff < 0 then
    	bee.setText(self.DetailTimeText, "<color=#da2352>" .. DispatchModel:getDispatchTimeText1(dt) .. "</color>")
    elseif timeBuff > 0 then
    	bee.setText(self.DetailTimeText, "<color=#66e742>" .. DispatchModel:getDispatchTimeText1(dt) .. "</color>")
    else
    	bee.setText(self.DetailTimeText, DispatchModel:getDispatchTimeText1(dt))
    end
    

    self.ReselectButton:SetActive(role_id ~= nil)
end

function P:onClickDispatchButton()
	local roles = {}
	for k, v in pairs(self.selectedRoleList) do
		table.insert(roles, v)
	end

	local selectedCount = #roles
	if selectedCount == 0 then
		UiManager:showToast(_T("LAB_DISPATCH_87"))
		return
	elseif selectedCount < self._maxRoleCount and LocalStore:isDailyTagValidCrossDay("DispatchSelectionTips", true) then
		local params = {}
		params.text = _T("LAB_DISPATCH_46")
		params.onSure = function(isOn)
			DispatchModel:reqDispatch(self._eventId, roles, self._params.item_id)
			if isOn then
				LocalStore:isDailyTagValidCrossDay("DispatchSelectionTips")
			end
			self:hideUI()
		end
		params.toggle = true

		UiManager:showTip(params)
	else
		DispatchModel:reqDispatch(self._eventId, roles, self._params.item_id)
		self:hideUI()
	end
end

return P