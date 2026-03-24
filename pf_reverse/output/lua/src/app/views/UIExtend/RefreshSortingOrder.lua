local P = class("RefreshSortingOrder", Object)

function P:ctor(node)
	if node then
		self.node = node.gameObject or node
	end
end

function P:onAwake()
	self:refreshSortingOrder()
end

function P:refreshSortingOrder()
	local canvas = self.node.transform:GetComponentInParent(typeof(CS.UnityEngine.Canvas))
	local sortingOrderVal = canvas and canvas.sortingOrder or 1

	-- 刷新子节点Canvas层级
	local canvasList = self.node.transform:GetComponentsInChildren(typeof(CS.UnityEngine.Canvas))
	for i = 0, canvasList.Length - 1 do
		canvasList[i].sortingLayerName = "UI"
		canvasList[i].sortingOrder = canvasList[i].sortingOrder + sortingOrderVal
	end

	-- 子节点Renderer层级
	local rendererList = self.node.transform:GetComponentsInChildren(typeof(CS.UnityEngine.ParticleSystemRenderer))
	for i = 0, rendererList.Length - 1 do
		rendererList[i].sortingLayerName = "UI"
		rendererList[i].sortingOrder = rendererList[i].sortingOrder + sortingOrderVal
	end
end

