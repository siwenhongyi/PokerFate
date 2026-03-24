local P = class("CharacterMainIntroduction", UiDialog)

function P:onAwake()
	local AnimRoot = self:find("AnimRoot")
	local Center = self:find("Center", AnimRoot)

	self.CharacterImage = self:find("Cover/bg_mask/Mask/CharacterImage", Center)
	self.Text = self:find("Content/TextList/Viewport/Content/TEXT", Center)
	self.CloseButton = self:find("CloseButton", Center)
	
	bee.addClick(self.CloseButton, function()
		self:hideUI()
	end)
end

function P:onStart()
	self._role_id = self._params.roleId

	local cfg = tpl_character[self._role_id]
	bee.setText(self.Text, _T(cfg.introduce))
	local skins = get_tpl_subKey(tpl_character_skin_list, "role", self._role_id)
	bee.invoke(self.CharacterImage, "setSkinImage", skins[1])
end

