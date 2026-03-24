local ItemData = require("app.model.ItemData")
local P = class("ItemModel", BaseModel)

P.DecorateCfg = {
	[GPropKind.LobbyScene] = tpl_hall_scene,
	[GPropKind.Table] = tpl_card_table,
	[GPropKind.AllInEff] = tpl_all_in_anim,
}

-- 道具管理
function P:ctor(logic)
	self.saveData = {
		cloud = {
            -- newitems .. uid = {uniq_id, uniq_id},   -- 新道具
        }
	}

    P.super.ctor(self)

	self._items = {}
	self._itemMap = {}
    self._defaultItems = {}	-- 默认锁定物品

	-- 外显使用 id
    self.using_card_back = 0 -- 当前使用中的牌桌
    self.using_table = 0 -- 当前使用中的牌桌
    self.using_lobby_music = 0 -- 当前使用中的大厅音乐
    self.using_battle_music = 0 -- 当前使用中的战斗音乐
    self.using_lobby_scene = 0 -- 当前使用中的大厅场景

	self.OutFitsKind = {
		using_card_back = GPropKind.CardBack,
		using_table = GPropKind.Table,
		using_lobby_music = GPropKind.MusicLobby,
		using_battle_music = GPropKind.MusicTable,
		using_lobby_scene = GPropKind.LobbyScene,
	}

	self._newitems = nil
end

function P:afterLogin()
    if not self.cloud["newitems" .. PlayerModel:getUid()] then
        self.cloud["newitems" .. PlayerModel:getUid()] = {}
    end
    self._newitems = self.cloud["newitems" .. PlayerModel:getUid()]

	self:clearItems()
end

function P:clearItems()
	self._items = {}
	self._itemMap = {}
end

function P:setItems(items)
	for _, v in ipairs(items) do
		local d = self._itemMap[v.item_uniq_id]
		if d then
			d:setData(v)
		else
			self:addItem(v)
		end
	end
	
	self:refreshReddot()
end

function P:setOwnedItems(owned_item_list)
	self._owned_item_dic = {}
	if owned_item_list then
		for k,v in pairs(owned_item_list) do
			self._owned_item_dic[v] = true
		end
	end
	for k,v in pairs(tpl_props) do
		if v.newTagHide then
			self._owned_item_dic[v.id] = true
		end
	end
end

function P:addItem(item)
	if not tpl_props[item.item_id] then
		return
	end
	local itemData = self._defaultItems[item.item_id]
	if not itemData then
		itemData = ItemData:create(item)
	else
		self._defaultItems[item.item_id] = nil
		itemData:setData(item)
	end
	if not itemData._no_data then
		table.insert(self._items, itemData)
		self._itemMap[itemData.item_uniq_id] = itemData
		return itemData
	end
end

function P:getItems()
	return self._items
end

function P:refreshItems(items)
	for _, v in ipairs(items) do
		local d = self._itemMap[v.item_uniq_id]
		if d then
			d.num = v.num
			d.deadline = v.deadline
			if d.num <= 0 then
				self._itemMap[v.item_uniq_id] = nil
				for k, v in ipairs(self._items) do
					if v == d then
						table.remove(self._items, k)
						break
					end
				end
			end
		elseif (v.num and v.num > 0) then
			d = self:addItem(v)
		end
		if d then
			bee.emit(EventDef.evt_item_refresh, d)
		end
	end
end

-- 获取普通道具
function P:getItem(conf_id, def)
	if conf_id == GPropId.Gold then
		return self:getItemData(GPropId.Gold, PlayerModel:getGold())
	end
	for _, v in ipairs(self._items) do
		if v.item_id == conf_id then
			return v
		end
	end
	if def then
		if not self._defaultItems[conf_id] then
			self._defaultItems[conf_id] = ItemData:create({
				item_id = conf_id,
				item_uniq_id = -conf_id,
				num = 0,
				locked = true,
			})
		end
		return self._defaultItems[conf_id]
	end
	return nil
end

-- 获取普通道具数量
function P:getItemNumById(conf_id)
	local item = self:getItem(conf_id)
	if not item then
		return 0
	end

	return item.num or 0
end

-- 获取 kind 类型的物品总数
function P:getItemTotalNumByKind(kind)
	local ret = 0
	for _, v in ipairs(self._items) do
		if v.type == kind then
			ret = ret + v.num
		end
	end
	return ret
end

function P:getItemDecorationNum()
	local ret = 0
	for _, v in ipairs(self._items) do
		if v.type ~= GPropKind.Title and v.type >= GPropKind.Avatar and v.type <= GPropKind.LobbyScene then
			ret = ret + v.num
		end
	end
	return ret
end

function P:getItemById(uniq_id)
	return self._itemMap[uniq_id]
end

-- 获取道具数量
function P:getItemNumByUniqId(uniq_id)
	local item = self:getItemById(uniq_id)
	if not item then
		return 0
	end
	return item.num
end

function P:getTimeStr(dt, isCd)
	if dt >= 3600 then
		if dt % 3600 == 0 then
			return _F("LAB_TIME_H", math.floor(dt / 3600))
		end
		if isCd then
			return _F("LAB_TIME_H_PLUS", math.floor(dt / 3600), math.floor((dt % 3600) / 60))
		end
		return _F("LAB_CD_HM", math.floor(dt / 3600), math.floor((dt % 3600) / 60))
	elseif dt >= 60 then
		if isCd then
			return string.format("%02d:%02d", math.floor(dt / 60), dt % 60)
		end
		if dt % 60 == 0 then
			return _F("LAB_TIME_M", math.floor(dt / 60))
		end
		return _F("LAB_TIME_M", math.floor(dt / 60), dt % 60)
	end
	return _F("LAB_CD_S", dt)
end

function P:getPropItemTimeStr(dt)
	if dt > 86400 then
		local d = math.ceil(dt / 86400)
		return _F("LAB_TIME_DAY", d)
	elseif dt > 3600 then
		local h = math.ceil(dt / 3600)
		return _F("LAB_TIME_HOURS", h)
	else
		local m = math.ceil(dt / 60)
		return _F("LAB_TIME_MINUTES", m)
	end
end

function P:_isInList(val, list)
	if not list then
		return false
	end

	for k, v in pairs(list) do
		if v == val then
			return true
		end
	end
	return false
end

-- 类型排序优先级
function P:_getTypeSort(propType)
	for i, v in ipairs(tpl_constdata.PropsTypeSort) do
		if v == propType then
			return i
		end
	end
	return 999
end

function P:_sortItemList(list)
	for _, v in ipairs(list) do
		v._sortScore = 100000
		if self:isNewItem(v.item_uniq_id, v.item_id, true) then
			v._sortScore = v._sortScore + 100000
		end
		if v.num > 0 then
			v._sortScore = v._sortScore + 10000
		end
		
		if v.item_id == self.using_card_back or
			v.item_id == self.using_table or
			v.item_id == self.using_lobby_music or
			v.item_id == self.using_battle_music or
			v.item_id == self.using_lobby_scene then
			v._sortScore = v._sortScore + 10000
		end
	end
	local sortFunc = function(a, b)
		local sumA = a._sortScore
		local sumB = b._sortScore

		if a.typeSort < b.typeSort then
			sumA = sumA + 1000
		end
		if b.typeSort < a.typeSort then
			sumB = sumB + 1000
		end

		if a.cfg.quality > b.cfg.quality then
			sumA = sumA + 100
		end
		if b.cfg.quality > a.cfg.quality then
			sumB = sumB + 100
		end

		if a.cfg.bagIndex < b.cfg.bagIndex then
			sumA = sumA + 10
		end
		if b.cfg.bagIndex < a.cfg.bagIndex then
			sumB = sumB + 10
		end

		if a.item_id < b.item_id then
			sumA = sumA + 1
		end
		if b.item_id < a.item_id then
			sumB = sumB + 1
		end

		return sumA > sumB
	end

	table.sort(list, sortFunc)
end

-- 获取（已获得）普通道具列表
function P:getPropItems()
	local list = {}
	for k, v in pairs(self._items) do
		local cfg = tpl_props[v.item_id]
		if cfg and cfg.bagShow == 1 and v.num and v.num > 0 and self:_isInList(cfg.type, tpl_backpack[1].props_type) then
			local isCanShow = true
			if v.deadline and v.deadline > 0 and v.deadline < bee.getServerTime() then
				isCanShow = false
			end
			if isCanShow then
				local data = {}
				for k1, v1 in pairs(v) do
					data[k1] = v1
				end
				data.cfg = cfg
				data.typeSort = self:_getTypeSort(cfg.type)
				table.insert(list, data)
			end
		end
	end
	-- 金币
	if PlayerModel:getGold() > 0 then
		table.insert(list, {item_id = GPropId.Gold, num = PlayerModel:getGold(), cfg = tpl_props[GPropId.Gold], typeSort = self:_getTypeSort(GPropKind.Gold)})
	end

	self:_sortItemList(list)
	return list
end

-- 是否可显示
function P:isCanShow(cfg)
	if cfg.bagShow ~= 1 then
		return false
	end
	if cfg.time_start then
		local curTime = bee.getServerTime()
		return curTime >= cfg.time_start or PlayerModel:isEventWhite()
	end
	return true
end

-- 获取全展示道具列表
function P:getAllShowItems(backpackId, showOwn)
	local list = {}
	for k, v in pairs(tpl_props) do
		if self:isCanShow(v) then
			if tpl_backpack[backpackId] and self:_isInList(v.type, tpl_backpack[backpackId].props_type) then
				local count = self:getItemNumById(v.id)
				if count > 0 then
					local data = {}
					for k1, v1 in pairs(self:getItem(v.id)) do
						data[k1] = v1
					end
					data.cfg = v
					data.typeSort = self:_getTypeSort(v.type)
					table.insert(list, data)
				elseif not showOwn then
					table.insert(list, {item_id = v.id, num = count, cfg = v, typeSort = self:_getTypeSort(v.type)})
				end
			end
		end
	end
	self:_sortItemList(list)
	return list
end

function P:getRecycleList(backpackId, quality)
	if backpackId == 2 then
		return self:getGiftRecycleList(quality)
	end
end

function P:getGiftRecycleList(quality)
	local list = {}
	for k, v in pairs(tpl_props) do
		if v.bagShow == 1 and v.type == GPropKind.Gift and ((not quality or quality == 0) or v.quality <= quality) then
			local count = self:getItemNumById(v.id)
			if v.isBinding ~= 1 and count > 0 then
				local data = {}
				for k1, v1 in pairs(self:getItem(v.id)) do
					data[k1] = v1
				end
				data.cfg = v
				data.typeSort = self:_getTypeSort(v.type)
				table.insert(list, data)
			end
		end
	end
	self:_sortItemList(list)
	return list
end

function P:getItemData(id, count, time)
	local data = {}
	data.item_id = id
	data.num = count or 1
	data.deadline = time
	
	return data
end

function P:getPropTypeCount(propType)
	local ownCount = 0
	local totalCount = 0

	for k, v in pairs(tpl_props) do
		if self:isCanShow(v) and v.type == propType then
			totalCount = totalCount + 1
			if self:getItemNumById(v.id) and self:getItemNumById(v.id) > 0 then
				ownCount = ownCount + 1
			end
		end
	end

	return ownCount, totalCount
end

function P:isOwned(id)
	return self._owned_item_dic[id]
end

function P:isNewItem(item_id, isRemove)
	for k, v in pairs(self._newitems) do
		if item_id == v then
			if isRemove then
				table.remove(self._newitems, k)
				self:onSave()
			end
			return true
		end
	end
	return false
end

-- 判断是否为新道具
function P:checkIsNewItem(id, isRefresh)
	if not tpl_props[id] then
		return false
	end
	if not self._owned_item_dic then
		return true
	end

	local isNew = not self._owned_item_dic[id]
	if isRefresh and isNew then
		self._owned_item_dic[id] = true
	end
	if isNew then
		local isIn = false
		for k,v in pairs(self._newitems) do
			if v == id then
				isIn = true
				break
			end
		end
		if not isIn then
			table.insert(self._newitems, id)
			self:onSave()
		end
	end

	return isNew
end

-- 获取当前背包页签包含的道具类型
function P:_getTabTogglePropTypes(id)
	local cfg = tpl_backpack[id]
	if not cfg then
		return {}
	end

	local propTypes = {}
	if cfg.show_type == 2 then
		for k, v in pairs(cfg.sub_page) do
			for k1, v1 in pairs(tpl_backpack[v].props_type) do
				table.insert(propTypes, v1)
			end
		end
	elseif cfg.props_type then
		propTypes = cfg.props_type
	end
	return propTypes
end

function P:refreshReddot()
	if not next(self._newitems) then
		for k,v in pairs(tpl_backpack) do
			if v.red_name then
				if v.id ~= 4 then
					RedManager:removeTag(RedTag[v.red_name])
				end
			end
		end
		return
	end

    local redList = {}
    for _, v in pairs(self._newitems) do
    	local d = self:getItem(v)
    	if d then
	    	for _, cfg in pairs(tpl_backpack) do
	    		if cfg.red_name then
	    			local propTypes = self:_getTabTogglePropTypes(cfg.id)
	    			if next(propTypes) then
    					if not redList[cfg.id] then
    						redList[cfg.id] = 0
    					end
		    			for k1, v1 in pairs(propTypes) do
		    				if v1 == d.type then
		    					redList[cfg.id] = redList[cfg.id] + 1
		    					break
		    				end
		    			end
		    		end
	    		end
	    	end
	    end
    end
    if next(redList) then
	    for k, v in pairs(redList) do
	    	if v > 0 then
	    		RedManager:addTag(RedTag[tpl_backpack[k].red_name])
	    	else
	    		RedManager:removeTag(RedTag[tpl_backpack[k].red_name])
	    	end
	    end
	else
		RedManager:removeTag(RedTag.Backpack)
	end
end

function P:removeRedTagByBackPackId(id)
	local count = #self._newitems
	if count <= 0 then
		return
	end

	local propTypes = self:_getTabTogglePropTypes(id)
	for i = count, 1, -1 do
		local d = tpl_props[self._newitems[i]]
		if d then
			for k, v in pairs(propTypes) do
				if d.type == v then
					table.remove(self._newitems, i)
					break
				end
			end
		else
			print("Nill Prop Id: " .. self._newitems[i])
			table.remove(self._newitems, i)
		end
	end
	self:onSave()

	self:refreshReddot()
end

function P:removeRedTagById(id)
	if not next(self._newitems) then
		return
	end
	for k, v in pairs(self._newitems) do
		if v == id then
			table.remove(self._newitems, k)
			break
		end
	end
	self:onSave()
	self:refreshReddot()
end

function P:setInfo(info)
    self.using_card_back = info.using_card_back
    self.using_table = info.using_table
    self.using_lobby_music = info.using_lobby_music
    self.using_battle_music = info.using_battle_music
    self.using_lobby_scene = info.using_lobby_scene
end

function P:reqUseItem(item)
	Net:sendReq("pb.ChangeOutFitsREQ", {
		item_type = item.type or (item.cfg and item.cfg.type),
		item_id = item.item_id,
	})
end

function P:reqChangeAnimation(item)
	local ftype
	if item.cfg.type == GPropKind.AllInEff then
		ftype = ACTION_TYPE.AllInEff
	elseif item.cfg.type == GPropKind.NameplateEff then
		ftype = ACTION_TYPE.NameplateEff
	elseif item.cfg.type == GPropKind.CardFace then
		ftype = ACTION_TYPE.CardFace
	end
	Net:sendReq("pb.ChangeAnimationREQ", {
		ftype = ftype,
		item_id = item.cfg.id,
	})
end

function P:setOutFits(msg)
	for k, v in pairs(self.OutFitsKind) do
		if v == msg.item_type then
			self[k] = msg.item_id
			if k == "using_lobby_scene" then
				bee.emit(EventDef.evt_refreshLobbyScene)
			elseif k == "using_lobby_music" then
				bee.emit(EventDef.evt_refreshLobbyMusic)
			end
			break
		end
	end
end

-- 获取跳转id
function P:_getJumpId(jumpCfg, jumpId)
	if not jumpId then
		return
	end

	local propCfg = tpl_props[jumpId]
	if not propCfg then
		return jumpId
	end

	-- 道具跳转根据类型和跳转界面传入对应跳转id
	if propCfg.type == GPropKind.Avatar then
		-- 头像跳转
		if jumpCfg.view == "GachaMain" or jumpCfg.view == "CharacterMainBonds" then
			jumpId = tpl_character_skin[propCfg.mapId].role
		elseif jumpCfg.view == "Shop" and jumpCfg.sub_page and jumpCfg.sub_page[1] == 2 then
			jumpId = tpl_character_skin[propCfg.mapId].id
		end
	elseif propCfg.type == GPropKind.FrameAvatar then
		-- 头像框
		if jumpCfg.view == "CharacterMainBonds" then
			jumpId = propCfg.mapId
		end
	elseif propCfg.type == GPropKind.Title then
		-- 称号
		if jumpCfg.view == "CharacterMainBonds" then
			jumpId = tpl_avatartitle[propCfg.mapId].character
		end
	end
	return jumpId
end

-- 是否可跳转
function P:isCanJump(accesses, id)
	if not accesses then
		return false
	end
	local jumpList = type(accesses) == "table" and accesses or {accesses}
	for _, jumpId in pairs(jumpList) do
		local jumpCfg = tpl_Jump_path[jumpId]
		if not jumpCfg then
			return false
		end

		local isOpen = true
		if jumpCfg.theme_activity_id then
			-- 关联活动则判断活动是否开启
			if not ActivityManager:isActivityOpen(ActivityId.Theme, jumpCfg.theme_activity_id) then
				isOpen = false
				break
			end
		end
		if isOpen then
			if jumpCfg.view == "Shop" then
				if jumpCfg.sub_page and jumpCfg.sub_page[1] == 2 then
					-- 皮肤商城
					return ShopModel:getIsInShopSkin(self:_getJumpId(jumpCfg, id))
				elseif jumpCfg.sub_page and jumpCfg.sub_page[1] == 6 then
					-- 装饰商城
					if jumpCfg.sub_page[2] == 601 then
						local list = ShopModel:getThemeList()
						for k, v in pairs(list) do
							for i = 1, #v.props, 2 do
								local cfg = ShopModel.SHOP_TYPE_CFG[v.props[i]][v.props[i + 1]]
								if cfg.props[1] == id then
									return true
								end
							end
						end
					else
						local list = ShopModel:getDecorateList()
						for k,v in pairs(list) do
							if v.cfg.props[1] == id then
								return true
							end
						end
					end
				else
					return true
				end
			elseif jumpCfg.view == "GachaMain" and not jumpCfg.select then
				return GachaModel:getContainCardPoolId(self:_getJumpId(jumpCfg, id))
			else
				return true
			end
		end
	end
	return false
end

function P:jumpViewByItemId(id)
	local d = tpl_props[id]
	if d and d.accesses then
		self:jumpView(d.accesses[1], id)
	end
end

-- 道具跳转
function P:jumpView(id, jumpId, preHideCb)
	local jumpCfg = tpl_Jump_path[id]
	if jumpCfg.func_id then
		-- 判断系统是否开启
		local funcCfg = tpl_system_info[jumpCfg.func_id]
		if PlayerModel:getCurLevel() < funcCfg.level then
			UiManager:showToast(_F("LAB_LEVEL_TEXT_1", funcCfg.level))
			return
		end
	end

	jumpId = self:_getJumpId(jumpCfg, jumpId)

	-- 跳转到相同界面时先关闭界面，避免界面刷新问题
	if UiManager:getUI(jumpCfg.view) then
		UiManager:hideUIForce(jumpCfg.view)
	end
	UiManager:showUI(jumpCfg.view, {jump = jumpCfg, jumpId = jumpId, preHideCb = preHideCb})
end

-- 判断是否为装饰类型
function P:getGPropType(propType)
	local n = math.floor(propType / 100)
	if n == 1 then
		return GPropType.Consume
	elseif n == 2 then
		return GPropType.Display
	end
end

function P:onPreview(data, cb)
	if data.type == GPropKind.CardBack or data.type == GPropKind.Table or data.type == GPropKind.Title then
		UiManager:showUI("BackpackPreview", {data = data})
	elseif data.type == GPropKind.MusicLobby or data.type == GPropKind.MusicTable then
		UiManager:showUI("BackpackMusic", {data = data, cb = cb})
	elseif data.type == GPropKind.LobbyScene then
		UiManager:showUI("BackpackLobbyPreview", {data = data, cb = cb})
	end
end

function P:reqUseTreasureBox(id, count, req_reward_list)
	Net:sendReq("pb.UseTreasureBoxREQ", {
		req_item = {
			item_uniq_id = id,
			item_num = count or 1,
		},
		req_reward_list = req_reward_list or {},
	})
end

function P:evt_UseTreasureBoxRSP(msg)
	local showRewardList = {}
	local showNewList = {}

	if msg.reward_role_list then
		for i,v in ipairs(msg.reward_role_list) do
			v.new = not CharacterModel:getRole(v.org_item.item_id)
			v.org_item.major_type = GMajorType.ROLE
			table.insert(showNewList, v)
			table.insert(showRewardList, v)
		end
	end
	if msg.reward_skin_list then
		for i,v in ipairs(msg.reward_skin_list) do
			v.new = not CharacterModel:isOwnedSkin(v.org_item.item_id)
			v.org_item.major_type = GMajorType.ROLE_SKIN
			table.insert(showNewList, v)
			table.insert(showRewardList, v)
		end
	end
	if msg.reward_prop_list then
		for i,v in ipairs(msg.reward_prop_list) do
			table.insert(showRewardList, v)
		end
	end

    if next(showNewList) then
        UiManager:showUI("GachaResultShow", {showList = showNewList, closeCb = function()
            UiManager:showUI("BackpackClaimResult", {items = showRewardList})
        end})
    else
        UiManager:showUI("BackpackClaimResult", {items = showRewardList})
    end
end

-- 请求刷新过期道具
function P:requestRefreshItem()
	Net:sendReq("pb.RefreshItemREQ", {})
end

-- 获得初始默认装饰
function P:getDefaultDecoration(propKind)
	for i = 1, #tpl_constdata.InitialProps, 2 do
		local propId = tpl_constdata.InitialProps[i]
		if tpl_props[propId].type == propKind then
			return tpl_props[propId].id
		end
	end
end

-- 请求使用经验卡
function P:requestUseExpCard(id, count)
	Net:sendReq("pb.UseExpItemREQ", {
		req_item = {
			item_uniq_id = id,
			item_num = count or 1,
		},
	})
end

function P:evt_UseExpItemRSP(msg)
	if msg.code ~= 0 then
		return
	end

	UiManager:showToast(_F("LAB_BACKPACK_TIPS_4", msg.exp_inc))
end

function P:getItemDesText(id)
	local cfg = tpl_props[id]
	if cfg.type == GPropKind.Gift then
		return _F(cfg.des, cfg.values[1], cfg.values[1] * 2)
	elseif 	cfg.type == GPropKind.ExpCard then
		return _F(cfg.des, cfg.values[1])
	else
		return _T(cfg.des)
	end
end

function P:evt_ItemChangeRSP(msg)
	if msg.item_list then
		for k, v in pairs(msg.item_list) do
			if v.num <= 0 then
				self:removeRedTagById(v.item_id)
			end
		end
	end
end

function P:evt_SelfUserInfoRSP()
	if not next(self._itemMap) then
		return
	end
	-- 头像
	if ItemModel:getItemNumById(PlayerModel:getAvatar()) == 0 then
		PlayerModel._avatar = tpl_constdata.DefaultAvatar
	end
	-- 头像框
	if ItemModel:getItemNumById(PlayerModel:getTitle()) == 0 then
		PlayerModel._title = 0
	end
	-- 称号
	if ItemModel:getItemNumById(PlayerModel:getFrame()) == 0 then
		PlayerModel._frame = 0
	end
end

