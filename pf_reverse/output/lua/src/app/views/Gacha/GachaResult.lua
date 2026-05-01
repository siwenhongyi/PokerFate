local P = class('GachaResult', UiFullView)

local GrideBg = {
	-- [0] = "Gacha[gacha_result_grid_02]",
	[1] = "Gacha[gacha_result_grid_02]",
	[2] = "Gacha[gacha_result_grid_03]",
	[3] = "Gacha[gacha_result_grid_04]",
	[4] = "Gacha[gacha_result_grid_05]",
	-- [5] = "Gacha[gacha_result_grid_02]",
}

local ItemPosList = {
	[1] = {x = -499, y = 244},
	[2] = {x = -222, y = 244},
	[3] = {x = 55, y = 244},
	[4] = {x = 332, y = 244},
	[5] = {x = 609, y = 244},
	[6] = {x = -602, y = -160},
	[7] = {x = -325, y = -160},
	[8] = {x = -48, y = -160},
	[9] = {x = 229, y = -160},
	[10] = {x = 506, y = -160},
}

function P:onAwake()
	self.AnimRoot = self:find("AnimRoot")

	self.Center = self:find("Center", self.AnimRoot)
	self.RightTop = self:find("RightTop", self.AnimRoot)
	self.RightBottom = self:find("RightBottom", self.AnimRoot)

	self.ConfirmButton = self:find("ConfirmButton", self.Center)
	self.RecruitButton = self:find("RecruitButton", self.Center)
	self.DrawText = self:find("DrawText", self.RecruitButton)
	self.DrawCont = self:find("DrawCont", self.Center)
	self.DrawTicket = self:find("DrawTicket", self.DrawCont)
	self.DrawCoin = self:find("DrawCoin", self.DrawCont)
	self.ExchangeCoinIcon = self:find("GachaCurrency/Ani_root/ExchangeCoinIcon", self.RightTop)
	self.ExchangeCoinText = self:find("GachaCurrency/Ani_root/ExchangeCoinText", self.RightTop)
	self.ShareCont = self:find("ShareCont", self.RightBottom)
	self.ShareButton = self:find("ShareButton", self.ShareCont)
	self.ShareReward = self:find("ShareReward", self.ShareCont)

	self.ItemCont = self:find("ItemCont", self.Center)
	self.ShowItem = self:find("ShowItem", self.ItemCont)
	self.ShowItem:SetActive(false)

	bee.addClick(self.ConfirmButton, function()
		Game:playSound("ui_button_confirm")
		Game:playLobbyBGM()
		self:closeUI(true)
		if CharacterModel:isGetNewRole() then
			SdkHelper:startAppReview()
		end
	end)
	bee.addClick(self.RecruitButton, function()
		self:onClickRecruit()
	end)
	bee.addClick(self.ShareButton, function()
		UiManager:showUI("ShareMain", {id = 3})
	end)

	self.transItemList = {}
end

function P:onStart()
	self._recruitNum = self._params.num
	self._showList = self._params.list
	self:showContent()
	self:setButtonShow()

	self.ShareCont:SetActive(not self._params.isGuide)

	bee.setIconInAtlas(self.ExchangeCoinIcon, tpl_props[tpl_constdata.CharacterDropRewards].icon)
	bee.setText(self.ExchangeCoinText, "x" .. self._recruitNum)

	if self._params.isGuide then
		self.DrawCont:SetActive(false)
		self.RecruitButton:SetActive(false)
		self:find("GachaCurrency", self.RightTop):SetActive(false)
		local pos = self.ConfirmButton.transform.localPosition
		pos.x = 0
		self.ConfirmButton.transform.localPosition = pos
	end
	
	self:setShareCont()
end

function P:evt_ItemChangeRSP(msg)
    self:setButtonShow()
end

function P:showContent()
	if self._recruitNum == 1 then
		Game:playSound("sound_recruit_show")
		self.ShowItem:SetActive(true)
		self:setShowItem(self.ShowItem, self._showList[1])
		self:once(0.2, function()
			self.ShowItem:SetActive(true)
		end)
		self:once(1.2, function()
			self:setTransAnim()
		end)
	else
		Game:playSound("sound_recruit_showall")
		for i = 1, 10 do
			local item = CU.GameObject.Instantiate(self.ShowItem)
			item.transform:SetParent(self.ItemCont.transform)
			item.transform.localPosition = bee.v3(ItemPosList[i].x, ItemPosList[i].y, 0)
			item.transform.localScale = bee.v3(1, 1, 1)

			self:setShowItem(item, self._showList[i])
			self:once(0.1 * i, function()
				item:SetActive(true)
			end)
			self:once(2, function()
				self:setTransAnim()
			end)
		end
	end
end

function P:setShowItem(item, data)
	local RoleBg = self:find("RoleBg", item)
	local Character = self:find("RoleBg/Character/Character", item)
	local CharacterImage = self:find("RoleBg/Character/Character/CharacterImage", item)
	local ItemBg = self:find("ItemBg", item)
	local ItemIcon = self:find("ItemBg/ItemIcon", item)
	local NameText = self:find("ItemBg/NameText", item)
	local NewIcon = self:find("NewIcon", item)

	local TransMask = self:find("TransMask", item)
	local TransMas_Ani = self:find("TransMas_Ani", TransMask)
	local TransBg = self:find("TransBg", TransMas_Ani)
	local TransItemIcon = self:find("TransItemIcon", TransMas_Ani)
	local TransCountText = self:find("TransCountText", TransMas_Ani)
	local TransNameText = self:find("TransNameText", TransMas_Ani)
	TransMask:SetActive(false)

	if data.content_type == CARD_CONTENT_TYPE.CHARACTER then
		RoleBg:SetActive(true)
		ItemBg:SetActive(false)

		local cfg = tpl_character[data.content_id]
		local showSkin = get_tpl_subKey(tpl_character_skin_list, "role", data.content_id)[1]
		bee.setIconInAtlas(CharacterImage, showSkin.table_avatar_pic, true)
		local offset = showSkin.table_avatar_offset or {36, 0, 1.2}
		CharacterImage.transform.localPosition = bee.v3(offset[1], offset[2], 0)
		CharacterImage.transform.localScale = bee.v3(offset[3], offset[3], 1)

		if bee.isIos or bee.isEditor then
			bee.convertMaskToSoftMask(Character)
		end

		bee.removeAllClick(CharacterImage)
		bee.addClick(CharacterImage, function()
			if not self._params.isGuide then
				Game:playSound("ui_button_confirm")
				UiManager:showUI("CharacterMainProfile", {data = CharacterModel:getRoleData(data.content_id)})
			end
		end)
	else
		RoleBg:SetActive(false)
		ItemBg:SetActive(true)

		local cfg = tpl_props[data.content_id]
		for i = 1, 4 do
			self:find("Bg" .. i, ItemBg):SetActive(i == cfg.quality)
		end
		bee.setIconInAtlas(ItemIcon, cfg.icon, true)
		bee.setText(NameText, _T(cfg.name))
	end

	NewIcon:SetActive(data.new)
	if data.new then
		local efc = AnimationMgr:playUIEffect("Prefab/Eff_poker_Ui_new_loop", NewIcon.transform, bee.v3(0, 0, 0), -1)
		efc.transform.localScale = bee.v3(0.5, 0.5, 0.5)
	end

	local transInfo
	if not data.new then
		if data.content_type == CARD_CONTENT_TYPE.CHARACTER then
			local cfg = tpl_character[data.content_id]
			transInfo = cfg.frag_num
		else
			local cfg = tpl_props[data.content_id]
			if data.content_type == CARD_CONTENT_TYPE.DECORATION then
				transInfo = cfg.decProps
			end
		end
	end
	if transInfo then
		local transCfg = tpl_props[transInfo[1]]
		for i = 1, 4 do
			self:find("Bg" .. i, TransBg):SetActive(i == transCfg.quality)
		end
		bee.setIconInAtlas(TransItemIcon, transCfg.icon)
		bee.setText(TransCountText, "X" .. transInfo[2])
		bee.setText(TransNameText, _T(transCfg.name))
		table.insert(self.transItemList, item)
	end

	bee.removeAllClick(item)
	bee.addClick(item, function()
		local id = data.content_id
		if not data.new and transInfo then
			id = transInfo[1]
		elseif data.content_type == CARD_CONTENT_TYPE.CHARACTER then
			return
		end
		Game:playSound("ui_button_confirm")
		if self._recruitNum == 1 and bee.isLongScreen then
			UiManager:showUI("CommonItemTipLR", {data = ItemModel:getItem(id, true), target = ItemBg})
		else
			UiManager:showUI("CommonItemTip", {data = ItemModel:getItem(id, true), target = ItemBg})
		end
	end)
end

function P:setTransAnim()
	if not next(self.transItemList) then
		return
	end

	for _, item in pairs(self.transItemList) do
		local TransMask = self:find("TransMask", item)
		TransMask:SetActive(true)
		Game:playSound("sound_recruit_fragment")

		local showTrans = true
		self:schedule(3, function()
			showTrans = not showTrans
			if showTrans then
				item:GetComponent("Animator"):Play("UI_1_GachaResult_Itemsingle_switch01")
			else
				item:GetComponent("Animator"):Play("UI_1_GachaResult_Itemsingle_switch02")
			end
		end)
	end
end

function P:setButtonShow()
    local drawCoin = tpl_constdata.CharacterDropCoin
    local drawCoinTen = tpl_constdata.CharacterDropCoinTen
    local drawTicket = tpl_constdata.CharacterDropTicket

    local curCoinCount = ItemModel:getItemNumById(GPropId.DrawCoin)
    local curTicketCount = ItemModel:getItemNumById(GPropId.DrawTicket)

	bee.setIconInAtlas(self:find("DrawIcon", self.DrawCoin), tpl_props[GPropId.DrawCoin].icon)
	bee.setIconInAtlas(self:find("DrawIcon", self.DrawTicket), tpl_props[GPropId.DrawTicket].icon)

    if self._recruitNum == 1 then
    	-- 单抽
    	bee.setText(self.DrawText, _T("LAB_GACHA_003"))

    	if curTicketCount >= 1 then
    		self.DrawCoin:SetActive(false)
    		self.DrawTicket:SetActive(true)
    		bee.setText(self:find("DrawText", self.DrawTicket), "x1")
    		self:find("DrawText", self.DrawTicket):SetActive(true)
    		self:find("DrawRedText", self.DrawTicket):SetActive(false)
    	elseif curCoinCount >= tonumber(drawCoin[2]) then
    		self.DrawCoin:SetActive(true)
    		self.DrawTicket:SetActive(false)
    		bee.setText(self:find("DrawText", self.DrawCoin), "x" .. tonumber(drawCoin[2]))
    	else
    		self.DrawCoin:SetActive(false)
    		self.DrawTicket:SetActive(true)
    		bee.setText(self:find("DrawRedText", self.DrawTicket), "x1")
    		self:find("DrawText", self.DrawTicket):SetActive(false)
    		self:find("DrawRedText", self.DrawTicket):SetActive(true)
    	end
    else
    	-- 十抽
    	bee.setText(self.DrawText, _T("LAB_GACHA_004"))

	    if curTicketCount >= 10 then
	        -- 芯片足够10抽
	        self.DrawCoin:SetActive(false)
	        self.DrawTicket:SetActive(true)
	        bee.setText(self:find("DrawText", self.DrawTicket), "x10")
	        self:find("DrawText", self.DrawTicket):SetActive(true)
	        self:find("DrawRedText", self.DrawTicket):SetActive(false)
	    else
	        if curTicketCount >= 1 then
	            -- 还有芯片时优先判断是否可靠水晶补齐
	            local lackTicket = 10 - curTicketCount
	            local lackCount = (drawCoinTen[2] / 10) * lackTicket
	            if lackCount <= curCoinCount then
	                -- 足够水晶补齐
	                self.DrawCoin:SetActive(true)
	                self.DrawTicket:SetActive(true)
	                bee.setText(self:find("DrawText", self.DrawCoin), "x" .. lackCount)
	                bee.setText(self:find("DrawText", self.DrawTicket), "x" .. curTicketCount)
	                self:find("DrawText", self.DrawTicket):SetActive(true)
	                self:find("DrawRedText", self.DrawTicket):SetActive(false)
	            else
	                -- 不够水晶补齐
	                self.DrawCoin:SetActive(false)
	                self.DrawTicket:SetActive(true)
	                bee.setText(self:find("DrawRedText", self.DrawTicket), "x10")
	                self:find("DrawText", self.DrawTicket):SetActive(false)
	                self:find("DrawRedText", self.DrawTicket):SetActive(true)
	            end
	        elseif curCoinCount >= tonumber(drawCoinTen[2]) then
	            -- 水晶足够10抽
	            self.DrawCoin:SetActive(true)
	            self.DrawTicket:SetActive(false)
	            bee.setText(self:find("DrawText", self.DrawCoin), "x" .. drawCoinTen[2])
	        else
	            self.DrawCoin:SetActive(false)
	            self.DrawTicket:SetActive(true)
	            bee.setText(self:find("DrawRedText", self.DrawTicket), "x10")
	            self:find("DrawText", self.DrawTicket):SetActive(false)
	            self:find("DrawRedText", self.DrawTicket):SetActive(true)
	        end
	    end
    end
end

function P:onClickRecruit()
	Game:playSound("ui_button_confirm")
	if not bee.checkCd("DrawCard", 2) then
		return
	end
	-- if bee.checkCd("DrawCard", 2) then
	-- 	-- 判断是否足够
	-- 	if self._recruitNum == 10 then
	-- 		GachaModel:checkRecruitTenCost(function(costList)
	-- 			self._costList = costList
	-- 			self:closeUI(true)
	-- 		end)
	-- 	else
	-- 		GachaModel:checkRecruitOneCost(function(costList)
	-- 			self._costList = costList
	-- 			self:closeUI(true)
	-- 		end)
	-- 	end
	-- end

    local drawCoin = tpl_constdata.CharacterDropCoin
    local drawCoinTen = tpl_constdata.CharacterDropCoinTen
    local curCoinCount = ItemModel:getItemNumById(GPropId.DrawCoin)
    local curTicketCount = ItemModel:getItemNumById(GPropId.DrawTicket)

    local costList = {}
    if self._recruitNum == 1 then
		if curTicketCount >= 1 then
	        table.insert(costList, {id = GPropId.DrawTicket, count = 1})
	    elseif curCoinCount >= tonumber(drawCoin[2]) then
	        table.insert(costList, {id = GPropId.DrawCoin, count = drawCoin[2]})
	    end
    else
    	if curTicketCount >= 10 then
	        -- 芯片足够10抽
	        table.insert(costList, {id = GPropId.DrawTicket, count = 10})
	    else
	        if curTicketCount >= 1 then
	            local lackTicket = 10 - curTicketCount
	            local lackCount = (drawCoinTen[2] / 10) * lackTicket
	            if lackCount <= curCoinCount then
	                -- 足够水晶补齐
	                table.insert(costList, {id = GPropId.DrawTicket, count = curTicketCount})
	                table.insert(costList, {id = GPropId.DrawCoin, count = lackCount})
	            end
	        elseif curCoinCount >= tonumber(drawCoinTen[2]) then
	            table.insert(costList, {id = GPropId.DrawCoin, count = drawCoinTen[2]})
	        end
	    end
    end

    -- 数量不足跳转获取
    if not next(costList) then
        -- 跳转提示
        local params = {}
        local propCfg = tpl_props[GPropId.DrawTicket]
        params.text = _F("LAB_GACHA_023", _T(propCfg.name))
        params.onSure = function()
            ItemModel:jumpView(propCfg.accesses[1])
        end
        UiManager:showTip(params)
        return
    end

	self._costList = costList
	self:closeUI(true)
end

function P:reRecruit()
	if self._costList and next(self._costList) then
		if self._recruitNum == 10 then
			GachaModel:recruitTen(self._params.pool_id, self._costList)
		else
			GachaModel:recruitOne(self._params.pool_id, self._costList)
		end
	end
end

function P:closeUI(noSound)
	if self._params.isGuide then
		self._closeAnim = ""
		self:hideUI(nil, noSound)
		return
	end

	for i = 1, self.ItemCont.transform.childCount do
		local showItem = self.ItemCont.transform:GetChild(i - 1)
		showItem:GetComponent("Animator"):Play("UI_1_GachaResult_Itemsingle_back")
		self:find("TransMask/TransEff", showItem):SetActive(false)
	end
	if not GachaModel:getSkipAnimFlag() then
		self:reRecruit()
	end
	self._closeAnim = ""
	AnimationMgr:play(self.AnimRoot:GetComponent("Animator"), "UI_1_GachaResult_back", function()
		if not bee.isNull(self.node) then
			if GachaModel:getSkipAnimFlag() then
				self:reRecruit()
			end
			self:hideUI(nil, noSound)
		end
	end)
end

function P:evt_shareShot()
	self.RightTop:SetActive(false)
	self.RecruitButton:SetActive(false)
	self.ConfirmButton:SetActive(false)
	self.DrawCont:SetActive(false)

    self.ShareButton:SetActive(false)
    self.ShareReward:SetActive(false)
end

function P:evt_endShareShot()
	self.RightTop:SetActive(true)
	self.RecruitButton:SetActive(true)
	self.ConfirmButton:SetActive(true)
	self.DrawCont:SetActive(true)

    self.ShareButton:SetActive(true)
    self:setShareCont()
end

function P:evt_updateSharedPage()
    self:setShareCont()
end

function P:setShareCont()
    local Icon = self:find("Icon", self.ShareReward)
    local CountText = self:find("CountText", self.ShareReward)
    ShareModel:setShareCont(self.ShareReward, Icon, CountText, 3)
end

return P