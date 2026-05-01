local P = class("RoleItem", Object)
RoleItem = P

function P:ctor(node, data)
	if node then
		self.node = node.gameObject or node
		self:initUI()
	end
	if data then
		self:setData(data)
	end
end

function P:onAwake()
	self:initUI()
	self:on("init", function(data)
		self:setData(data)
	end)
end

function P:initUI()
	self.Bg = self:find("Bg")
	self.AvatarIcon = self:find("AvatarIcon")
end

function P:setData(data)
	self.data = data
	self.id = data.item_id or data.id

	-- 头像
	local cfg
	if data.major_type == GMajorType.ROLE then
		cfg = tpl_character[self.id]
	elseif data.major_type == GMajorType.ROLE_SKIN then
		cfg = tpl_character_skin[self.id]
	end
	local avatarCfg = tpl_props[cfg.avatar]
	bee.setIconInAtlas(self.AvatarIcon, avatarCfg.icon)
end

function P:bindDetail()
	bee.removeAllClick(self.node)
	bee.addClick(self.node, function()
		if self.data.major_type == GMajorType.ROLE then
			UiManager:showUI("CharacterMainProfile", {data = CharacterModel:getRoleData(self.id)})
		elseif self.data.major_type == GMajorType.ROLE_SKIN then
			local skinCfg = tpl_character_skin[self.id]
			UiManager:showUI("CharacterMainGarments", {data = CharacterModel:getRoleData(skinCfg.role), selectId = skinCfg.id})
		end
	end)
end

return P