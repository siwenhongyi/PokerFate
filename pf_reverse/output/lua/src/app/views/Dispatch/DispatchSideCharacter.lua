local P = class("DispatchSideCharacter", UiBase)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Left = self:find("Left", AnimRoot)

	self.CharacterListObj = self:find("CharacterList", Left)
	self.CharacterItem = self:find("CharacterItem", self.CharacterListObj)
	self.CharacterItem:SetActive(false)
	self.Empty = self:find("Empty", Left)

	local TabFilter = self:find("TabFilter", Left)
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

	self.CloseButton = self:find("CloseButton", Left)
	self.CloseMask = self:find("CloseMask", AnimRoot)

	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
	bee.addClick(self.CloseMask, function()
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

	self.filterItemList = {}
	self.characterTimeTag = {}
end

function P:onStart()
	self._selectFilterId = -1

	self:initCharacterList()
	self:setCharacterList()
	self:initFilter()
	self:refreshFilterCont()
end

function P:initCharacterList()
    self.charactetList = UiListEx:create(self.CharacterListObj)
    self.charactetList:setCreateFunc(function()
        return CU.GameObject.Instantiate(self.CharacterItem)
    end)
    self.charactetList:setRefreshFunc(function(data, item, isInit, index)
        self:setCharacterItem(item, data, isInit, index)
    end)
    self.charactetList:setWidth(218)
end

function P:setCharacterList()
    local list = {}
    for k, v in pairs(CharacterModel:getOwnedCharacters()) do
        if self._selectFilterId ~= -1 then
        	if v.info.campInt == self._selectFilterId then
        		table.insert(list, {role = v, dispatchData = DispatchModel:getDispatchRoleData(v.role_id)})
        	end
        else
            table.insert(list, {role = v, dispatchData = DispatchModel:getDispatchRoleData(v.role_id)})
        end
    end
    table.sort(list, function(a, b)
    	local sumA = 100
    	local sumB = 100

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

	if #list > 0 then
		self.CharacterListObj:SetActive(true)
		self.Empty:SetActive(false)
		self.charactetList:setDatas(list)
	else
		self.CharacterListObj:SetActive(false)
		self.Empty:SetActive(true)
	end
end

function P:setCharacterItem(item, data, isInit, index)
	local Ani_root = self:find("Ani_root", item)
	local Experience = self:find("Experience", Ani_root)
	local ExperienceSlider = self:find("ExperienceSlider", Experience)
	local CurText = self:find("CurText", Experience)
	local MaxText = self:find("MaxText", Experience)
	local Information = self:find("Information", Ani_root)
	local CampIcon = self:find("CampIcon", Information)
	local RoleNameText = self:find("RoleNameText", Information)
	local Stars = self:find("Stars", Information)
	local RewardBonus = self:find("Buff/RewardBonus", Information)
	local BaseRewardUp = self:find("Buff/BaseRewardUp", Information)
	local TimeReduce = self:find("Buff/TimeReduce", Information)
	local State = self:find("State", Ani_root)
	local Break = self:find("Break", State)
	local Dispatching = self:find("Dispatching", State)
	local TimeText = self:find("TimeText", Dispatching)
	local Leisure = self:find("Leisure", State)
	local SeniorNumText = self:find("Number/Senior/NumText", State)
	local OrdinaryNumText = self:find("Number/Ordinary/NumText", State)
	local AvatarIcon = self:find("Avatar/avatar_frame_01_mask/AvatarIcon", Ani_root)

    if isInit and index > 0 then
        self:once(0.1 * (index - 1), function()
            Ani_root:SetActive(true)
            self:playAnimator("UI_1_DispatchStar_item", Ani_root)
        end)
        Ani_root:SetActive(false)
    else
        Ani_root:SetActive(true)
        self:playAnimator("UI_1_DispatchStar_item_idle", Ani_root)
    end

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
	local nextLevelCfg = tpl_character_info[dispatchData.role_star + 1]

	if levelCfg.reward_bonus > 0 then
		RewardBonus:SetActive(true)
		bee.setText(self:find("NumText", RewardBonus), levelCfg.reward_bonus / 100 .. "%")
	else
		RewardBonus:SetActive(false)
	end
	if levelCfg.base_reward_up > 0 then
		BaseRewardUp:SetActive(true)
		bee.setText(self:find("NumText", BaseRewardUp), levelCfg.base_reward_up / 100 .. "%")
	else
		BaseRewardUp:SetActive(false)
	end
	if levelCfg.time_reduce > 0 then
		TimeReduce:SetActive(true)
		bee.setText(self:find("NumText", TimeReduce), levelCfg.time_reduce / 100 .. "%")
	else
		TimeReduce:SetActive(false)
	end

	if nextLevelCfg then
		MaxText:SetActive(false)
		CurText:SetActive(true)

		local curExp = dispatchData.exp
		for i, v in ipairs(tpl_character_info) do
			if v.level <= dispatchData.role_star then
				curExp = curExp - v.star_exp
			else
				break
			end
		end

		bee.setText(CurText, "<color=#C6C6C6>" .. _N(curExp) .. "</color>/" .. _N(nextLevelCfg.star_exp))
		bee.setSliderValue(ExperienceSlider, curExp / nextLevelCfg.star_exp)
	else
		MaxText:SetActive(true)
		CurText:SetActive(false)
		bee.setSliderValue(ExperienceSlider, 1)
	end

	local maxTimes = DispatchModel:getRoleDispatchMaxTimes(role.role_id)
	local remainTimes = dispatchData.remain_dispatch_times
	bee.setText(OrdinaryNumText, "<color=#C6C6C6>" .. remainTimes .. "</color>/" .. maxTimes)

	local seniorMaxTimes = tpl_constdata.Dispatch_Advanced_Num
	local seniorRemainTimes = dispatchData.remain_advanced_dispatch_times
	bee.setText(SeniorNumText, "<color=#C6C6C6>" .. seniorRemainTimes .. "</color>/" .. seniorMaxTimes)

    if self.characterTimeTag[item] then
        scheduler:removeTag(self.characterTimeTag[item])
        self.characterTimeTag[item] = nil
    end

	local dispatchEvent = DispatchModel:getRoleDispatchingEvent(role.role_id)
	if dispatchEvent then
		Dispatching:SetActive(true)
		Break:SetActive(false)
		Leisure:SetActive(false)

	    local time = dispatchEvent.end_ts - bee.getServerTime()
        if time > 0 then
            bee.setText(TimeText, DispatchModel:getDispatchTimeText2(time))
            self.characterTimeTag[item] = self:schedule(1, function()
                local time = dispatchEvent.end_ts - bee.getServerTime()
                if time > 0 then
                    bee.setText(TimeText, DispatchModel:getDispatchTimeText2(time))
                else
                    bee.setText(TimeText, _T("LAB_DISPATCH_17"))
                end
            end)
        else
            bee.setText(TimeText, _T("LAB_DISPATCH_17"))
        end
	else
		Dispatching:SetActive(false)
		if (remainTimes + seniorRemainTimes <= 0) or
			(seniorRemainTimes <= 0 and DispatchModel:getRemainOrdinaryTimes() <= 0 ) then
			Break:SetActive(true)
			Leisure:SetActive(false)
		else
			Break:SetActive(false)
			Leisure:SetActive(true)
		end

	end

	bee.removeAllClick(Dispatching)
	bee.addClick(Dispatching, function()
		bee.emit("evt_jumpDispatchEvent", {event = dispatchEvent})
		if UiManager:getUI("DispatchSeasonPass") then
			UiManager:hideUI("DispatchSeasonPass")
		end
	end)
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
			bee.logEvent("dispatch-my-character-filter", v.campInt)
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
		bee.logEvent("dispatch-my-character-filter", -1)
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

return P